import datetime
import json
from dataclasses import fields
from typing import Literal

import toml

from .backends import CONFIG_PATH, AsyncAPI, Backend, ProcessAPI
from .monitor_params import MonitorParameters


class MonitorInitializationError(Exception):
    """Custom exception for monitor initialization errors."""


BACKENDS = {"ProcessAPI": ProcessAPI, "AsyncAPI": AsyncAPI}
BackendTypes = Literal["ProcessAPI", "AsyncAPI"]
SignalTypes = Literal["NDVI"]
MetricTypes = Literal["RMSE"]
DatasourceTypes = Literal["S2L2A", "ARPS"]


def initialize_monitor(params: MonitorParameters, backend: BackendTypes, **kwargs) -> Backend:
    """
    Initialize a new monitor.

    Parameters:
        params (MonitorParameters): Parameters for the monitor.
        backend (BackendTypes): Backend type to use.
        **kwargs: Additional arguments for the backend.

    Returns:
        Backend: Initialized backend instance.
    """
    backend_instance = BACKENDS[backend](params, **kwargs)
    backend_instance.init_model()
    backend_instance.dump()
    return backend_instance


def start_monitor(
    name: str,
    monitoring_start: datetime.date,
    geometry: dict,
    resolution: float = 0.001,
    datasource: DatasourceTypes = "S2L2A",
    datasource_id: str | None = None,
    harmonics: int = 2,
    signal: SignalTypes = "NDVI",
    metric: MetricTypes = "RMSE",
    sensitivity: float = 5.0,
    boundary: float = 5.0,
    backend: BackendTypes = "ProcessAPI",
    overwrite: bool = False,
    load_only: bool = False,
    **kwargs,
) -> Backend:
    """
    Initialize disturbance monitoring

    This function is used to first initialize a disturbance monitor.
    The parameters used to initialize the monitor are saved in the config file
    at ~/.configs/disturbancemonitor/config.toml.

    During initializing, models will be fit for each pixel in the area of interest.
    This is the most processing intensive step of the monitoring. When loading
    the model later to actively monitor the area, this initializing will not be done
    again. Instead only the model weights are loaded.

    Args:
        name (str): Name of the monitor. Must be a unique name in the config file.
            Use `.load_monitor()` to load an already existing monitor.
        monitoring_start (datetime.date): Start of the monitoring. The model will
            be fit on the year before `monitoring_start`.
        geometry (dict): GeoJSON of the area to be monitored. Must be a single polygon.
        resolution (float): Resolution of a single pixel in degrees
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
    config = load_config()
    config_exists = name in config
    backend_exists = f"{name}.{backend}" in config
    is_initialized = config.get(name, {}).get("state") == "INITIALIZED"

    monitor_param_fields = {f.name for f in fields(MonitorParameters)}
    last_monitored = kwargs.pop("last_monitored", monitoring_start)
    filtered_monitor_kwargs = {k: v for k, v in kwargs.items() if k in monitor_param_fields}
    backend_kwargs = {k: v for k, v in kwargs.items() if k not in monitor_param_fields}

    params = MonitorParameters(
        name=name,
        monitoring_start=monitoring_start,
        geometry=geometry,
        resolution=resolution,
        datasource=datasource,
        datasource_id=datasource_id,
        harmonics=harmonics,
        signal=signal,
        metric=metric,
        sensitivity=sensitivity,
        boundary=boundary,
        last_monitored=last_monitored,
        **filtered_monitor_kwargs,
    )

    if load_only:
        return BACKENDS[backend](params, **backend_kwargs)

    if config_exists and backend_exists and is_initialized and not overwrite:
        raise MonitorInitializationError(
            f"Monitor with name '{name}' and backend '{backend}' already exists. "
            f"Use load_monitor('{name}', backend='{backend}') or set overwrite=True."
        )

    if overwrite:
        return initialize_monitor(params, backend, **backend_kwargs)

    return initialize_monitor(params, backend, **backend_kwargs)


def load_config() -> dict:
    """Loads config from toml file as dict"""
    config_toml = CONFIG_PATH / "config.toml"
    try:
        with open(config_toml) as configfile:
            return toml.load(configfile)
    except FileNotFoundError:
        CONFIG_PATH.mkdir(parents=True, exist_ok=True)
        config_toml.touch()
        return {}


def load_monitor(name: str, backend: BackendTypes = "ProcessAPI") -> Backend:  # TODO: backend sollte mit gedumpt werden
    """
    Load Monitor from config

    This loads a monitor object from the config file at
    ~/.disturbancemonitor/config.toml.

    Args:
        name (str): Name of the monitor, as saved in the config file
        backend (backend): Which backend to use for the monitor.
    """
    geom_out = CONFIG_PATH / "geoms"
    config = load_config()
    with open(geom_out / (name + ".geojson")) as fs:
        geometry = json.load(fs)
    return start_monitor(
        geometry=geometry,
        name=name,
        backend=backend,
        load_only=True,
        **config[f"{name}"],
        **config[f"{name}.{backend}"],
    )
