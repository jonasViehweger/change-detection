import datetime
from dataclasses import fields
from os import PathLike
from typing import Any, Literal

from .backends import AsyncAPI, Backend, ProcessAPI
from .constants import FEATURE_ID_COLUMN, EndpointTypes
from .geo_config_handler import GeoConfigHandler, get_geo_config
from .monitor_params import MonitorParameters


class MonitorInitializationError(Exception):
    """Custom exception for monitor initialization errors."""


BACKENDS = {"ProcessAPI": ProcessAPI, "AsyncAPI": AsyncAPI}
BackendTypes = Literal["ProcessAPI", "AsyncAPI"]
SignalTypes = Literal["NDVI"]
MetricTypes = Literal["RMSE"]
DatasourceTypes = Literal["S2L2A", "ARPS"]


def initialize_monitor(
    params: MonitorParameters,
    backend: BackendTypes,
    input_path: str | PathLike,
    id_column: str,
    config: GeoConfigHandler,
    **kwargs: Any,
) -> Backend:
    """
    Initialize a new monitor.

    Parameters:
        params (MonitorParameters): Parameters for the monitor.
        backend (BackendTypes): Backend type to use.
        input_path (str | PathLike): Path to the input geometry file.
        id_column (str): Name of the ID column in the geometry file.
        config (GeoConfigHandler): Configuration handler instance.
        **kwargs: Additional arguments for the backend.

    Returns:
        Backend: Initialized backend instance.
    """
    # Process the input geometry and store it in the GeoPackage
    # The geometry is stored in a layer named after the monitor
    config.prepare_geometry(input_path, id_column, params.name)

    # Set the geometry_path to point to the monitor name (layer in GeoPackage)
    params.geometry_path = params.name

    # Initialize the backend
    backend_instance = BACKENDS[backend](params, config=config, **kwargs)
    backend_instance.init_model()
    backend_instance.dump()
    return backend_instance


def start_monitor(
    name: str,
    monitoring_start: datetime.date,
    geometry_path: str | PathLike,
    id_column: str,
    resolution: float = 50,
    datasource: DatasourceTypes = "S2L2A",
    datasource_id: str | None = None,
    harmonics: int = 2,
    signal: SignalTypes = "NDVI",
    metric: MetricTypes = "RMSE",
    sensitivity: float = 5.0,
    boundary: float = 5.0,
    backend: BackendTypes = "ProcessAPI",
    endpoint: EndpointTypes = "SENTINEL_HUB",
    overwrite: bool = False,
    load_only: bool = False,
    config_file_path: str | PathLike | None = None,
    **kwargs: Any,
) -> Backend:
    """
    Initialize disturbance monitoring

    This function is used to first initialize a disturbance monitor.
    The parameters used to initialize the monitor are saved in the GeoPackage
    at ~/.configs/disturbancemonitor/monitor_config.gpkg.

    During initializing, models will be fit for each pixel in the area of interest.
    This is the most processing intensive step of the monitoring. When loading
    the model later to actively monitor the area, this initializing will not be done
    again. Instead only the model weights are loaded.

    Args:
        name (str): Name of the monitor. Must be a unique name in the GeoPackage.
            Use `.load_monitor()` to load an already existing monitor.
        monitoring_start (datetime.date): Start of the monitoring. The model will
            be fit on the year before `monitoring_start`.
        geometry_path (str | PathLike): Path to the geometry to use, must be a file format compatible with fiona.
            Only Polygons will be considered
        resolution (float): Resolution of a single pixel in meters
        datasource (str): Data source used for monitoring. One of "ARPS, S2L2A"
        harmonics (int): Number of harmonics. First order harmonics have a period of 1 year,
            second order a period of half a year and so on. Used during fitting of the model
        signal (str): Which signals to fit the model on. Must be "NDVI".
        metric (str): Metric to use as boundary condition.
        sensitivity (float): How sensitive the monitoring is to changes. The smaller the value the more sensitive.
            Everything larger than sensitivity*metric will be signaled as a possible disturbance
        boundary (float): Persistence of change. How many acquisitions in a row need to be
            identified as possible disturbance to confirm the disturbance.
        backend (Backend): One of ProcessAPI or AsyncAPI. Process API can only handle areas
            with less than 2500x2500 pixels and can time out. AsyncAPI can handle areas up to
            10000x10000 and doesn't time out as quickly.
        overwrite (bool): If an already existing monitor should be overwritten.
        config_file_path (str | PathLike | None): Optional path to custom config file.
            If None, uses default configuration.
    """
    # Get config instance
    config = get_geo_config(config_file_path)

    # Check if monitor exists in database
    monitor_exists, backend_exists_flag, is_initialized = config.backend_exists(name, backend)

    monitor_param_fields = {f.name for f in fields(MonitorParameters)}
    last_monitored = kwargs.pop("last_monitored", monitoring_start)
    filtered_monitor_kwargs = {k: v for k, v in kwargs.items() if k in monitor_param_fields}
    backend_kwargs = {k: v for k, v in kwargs.items() if k not in monitor_param_fields}

    params = MonitorParameters(
        name=name,
        monitoring_start=monitoring_start,
        geometry_path=name,  # Store just the name which will be used as the layer name in the GeoPackage
        resolution=resolution,
        datasource=datasource,
        datasource_id=datasource_id,
        harmonics=harmonics,
        signal=signal,
        metric=metric,
        sensitivity=sensitivity,
        boundary=boundary,
        last_monitored=last_monitored,
        endpoint=endpoint,
        **filtered_monitor_kwargs,
    )

    if load_only:
        config.save_monitor_params(params)
        return BACKENDS[backend](params, config=config, **backend_kwargs)

    if monitor_exists and backend_exists_flag and is_initialized and not overwrite:
        raise MonitorInitializationError(
            f"Monitor with name '{name}' and backend '{backend}' already exists. "
            f"Use load_monitor('{name}', backend='{backend}') or set overwrite=True."
        )

    if monitor_exists and backend_exists_flag and overwrite:
        # Load existing backend config
        backend_config = config.load_backend_config(name, backend)

        # Create backend instance with loaded config
        backend_instance = BACKENDS[backend](params, config=config, **backend_kwargs, **backend_config)
        print("Deleting resources")
        backend_instance.delete()
        return initialize_monitor(params, backend, geometry_path, id_column, config=config, **backend_kwargs)

    return initialize_monitor(params, backend, geometry_path, id_column, config=config, **backend_kwargs)


def load_monitor(
    name: str, backend: BackendTypes = "ProcessAPI", config_file_path: str | PathLike | None = None
) -> Backend:
    """
    Load Monitor from GeoPackage

    This loads a monitor object from the GeoPackage.

    Args:
        name (str): Name of the monitor, as saved in the GeoPackage
        backend (backend): Which backend to use for the monitor.
        config_file_path (str | PathLike | None): Optional path to custom config file.
            If None, uses default configuration.
    """
    # Get config instance
    config = get_geo_config(config_file_path)

    # Load monitor params and backend config from database
    monitor_config = config.load_monitor_params(name)
    backend_config = config.load_backend_config(name, backend)

    return start_monitor(
        backend=backend,
        id_column=FEATURE_ID_COLUMN,
        load_only=True,
        config_file_path=config_file_path,
        **monitor_config,
        **backend_config,
    )
