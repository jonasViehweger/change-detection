import datetime
from dataclasses import fields
from os import PathLike
from pathlib import Path
from typing import Any, Literal

import geopandas as gpd

from .backends import AsyncAPI, Backend, ProcessAPI
from .constants import CONFIG_PATH, FEATURE_ID_COLUMN, EndpointTypes
from .db import (
    backend_exists,
    init_db,
    load_backend_config,
    load_monitor_params,
    migrate_toml_to_sqlite,
    save_monitor_params,
)
from .monitor_params import MonitorParameters


class MonitorInitializationError(Exception):
    """Custom exception for monitor initialization errors."""


BACKENDS = {"ProcessAPI": ProcessAPI, "AsyncAPI": AsyncAPI}
BackendTypes = Literal["ProcessAPI", "AsyncAPI"]
SignalTypes = Literal["NDVI"]
MetricTypes = Literal["RMSE"]
DatasourceTypes = Literal["S2L2A", "ARPS"]


def initialize_monitor(
    params: MonitorParameters, backend: BackendTypes, input_path: str | PathLike, id_column: str, **kwargs: Any
) -> Backend:
    """
    Initialize a new monitor.

    Parameters:
        params (MonitorParameters): Parameters for the monitor.
        backend (BackendTypes): Backend type to use.
        input_path (str | PathLike): Path to the input geometry file.
        id_column (str): Name of the ID column in the geometry file.
        **kwargs: Additional arguments for the backend.

    Returns:
        Backend: Initialized backend instance.
    """
    # Convert path-like objects to strings
    input_path_str = str(input_path) if isinstance(input_path, PathLike) else input_path
    geometry_path_str = (
        str(params.geometry_path) if isinstance(params.geometry_path, PathLike) else params.geometry_path
    )

    prepare_geometry(input_path_str, id_column, geometry_path_str)
    backend_instance = BACKENDS[backend](params, **kwargs)
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
    **kwargs: Any,
) -> Backend:
    """
    Initialize disturbance monitoring

    This function is used to first initialize a disturbance monitor.
    The parameters used to initialize the monitor are saved in the SQLite database
    at ~/.configs/disturbancemonitor/config.db.

    During initializing, models will be fit for each pixel in the area of interest.
    This is the most processing intensive step of the monitoring. When loading
    the model later to actively monitor the area, this initializing will not be done
    again. Instead only the model weights are loaded.

    Args:
        name (str): Name of the monitor. Must be a unique name in the database.
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
    """
    # Initialize database and migrate existing TOML configs if needed
    init_db()

    # Check if it's the first time running with SQLite
    toml_config_path = CONFIG_PATH / "config.toml"
    if toml_config_path.exists():
        migrate_toml_to_sqlite()

    # Check if monitor exists in database
    monitor_exists, backend_exists_flag, is_initialized = backend_exists(name, backend)

    monitor_param_fields = {f.name for f in fields(MonitorParameters)}
    last_monitored = kwargs.pop("last_monitored", monitoring_start)
    filtered_monitor_kwargs = {k: v for k, v in kwargs.items() if k in monitor_param_fields}
    backend_kwargs = {k: v for k, v in kwargs.items() if k not in monitor_param_fields}
    geometry_out_path = CONFIG_PATH / "geoms" / f"{name}.gpkg"

    params = MonitorParameters(
        name=name,
        monitoring_start=monitoring_start,
        geometry_path=geometry_out_path,
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
        save_monitor_params(params)
        return BACKENDS[backend](params, **backend_kwargs)

    if monitor_exists and backend_exists_flag and is_initialized and not overwrite:
        raise MonitorInitializationError(
            f"Monitor with name '{name}' and backend '{backend}' already exists. "
            f"Use load_monitor('{name}', backend='{backend}') or set overwrite=True."
        )

    if monitor_exists and backend_exists_flag and overwrite:
        # Load existing backend config
        backend_config = load_backend_config(name, backend)

        # Create backend instance with loaded config
        backend_instance = BACKENDS[backend](params, **backend_kwargs, **backend_config)
        print("Deleting resources")
        backend_instance.delete()
        return initialize_monitor(params, backend, geometry_path, id_column, **backend_kwargs)

    return initialize_monitor(params, backend, geometry_path, id_column, **backend_kwargs)


def load_monitor(name: str, backend: BackendTypes = "ProcessAPI") -> Backend:
    """
    Load Monitor from database

    This loads a monitor object from the config database at
    ~/.disturbancemonitor/config.db.

    Args:
        name (str): Name of the monitor, as saved in the database
        backend (backend): Which backend to use for the monitor.
    """
    # Initialize database and migrate existing TOML configs if needed
    init_db()

    # Check if it's the first time running with SQLite
    toml_config_path = CONFIG_PATH / "config.toml"
    if toml_config_path.exists():
        migrate_toml_to_sqlite()

    # Load monitor params and backend config from database
    monitor_config = load_monitor_params(name)
    backend_config = load_backend_config(name, backend)

    return start_monitor(
        backend=backend,
        id_column=FEATURE_ID_COLUMN,
        load_only=True,
        **monitor_config,
        **backend_config,
    )


def prepare_geometry(geometry_path: str | PathLike, id_column: str, output_path: str | PathLike) -> None:
    """
    Load a geometry file, reproject it to EPSG:3857, set the column name to the id_column,
    check if all values in the id column are unique, and write it to a GeoPackage.

    Parameters:
    - geometry_path (str | PathLike): Path to the input geometry file.
    - id_column (str): The name of the column to be used as the ID column.
    - output_path (str | PathLike): Path to the output GeoPackage file.

    Returns:
    - None
    """
    # Convert path-like objects to strings
    geometry_path_str = str(geometry_path) if isinstance(geometry_path, PathLike) else geometry_path
    output_path_str = str(output_path) if isinstance(output_path, PathLike) else output_path

    # Load the input geometry with GeoPandas
    gdf = gpd.read_file(geometry_path_str).to_crs(epsg=3857).rename(columns={id_column: FEATURE_ID_COLUMN})

    # Add WGS84 centroid
    centroids = gdf.to_crs(epsg=4326).centroid
    gdf["lat"] = centroids.y
    gdf["lng"] = centroids.x

    # Check for any geometries which aren't POLYGONS
    if not all(gdf.geometry.type == "Polygon"):
        raise ValueError("All geometries must be of type POLYGON")

    # Check for uniqueness in the id_column
    is_unique = gdf[FEATURE_ID_COLUMN].is_unique
    if not is_unique:
        raise ValueError("Duplicate ID found")

    # Write out to GeoPackage
    output_path = Path(output_path_str)
    output_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure output directory exists
    gdf.to_file(output_path, driver="GPKG")
