import datetime
import json
from typing import Literal

import toml

from .backends import CONFIG_PATH, AsyncAPI, Backend, ProcessAPI
from .monitor_params import MonitorParameters

BACKENDS = {"ProcessAPI": ProcessAPI, "AsyncAPI": AsyncAPI}
_backend_types = Literal["ProcessAPI", "AsyncAPI"]


def start_monitor(
    name: str,
    monitoring_start: datetime.date,
    geometry: dict,
    resolution: float = 0.001,
    datasource: Literal["S2L2A", "ARPS"] = "S2L2A",
    datasource_id: str | None = None,
    harmonics: int = 2,
    signal: Literal["NDVI"] = "NDVI",
    metric: Literal["RMSE"] = "RMSE",
    sensitivity: float = 5,
    boundary: float = 5,
    backend: _backend_types = "ProcessAPI",
    overwrite: bool = False,
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
    state = kwargs.pop("state", "NOT_INITIALIZED")
    last_monitored = kwargs.pop("last_monitored", monitoring_start)
    unique_id = kwargs.pop("random_id", None)  # noqa: F841
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
        state=state,
        last_monitored=last_monitored,
    )
    config = load_config()
    config_exists = name in config
    backend_exists = name + "." + backend in config
    is_initialized = config.get(name, {}).get("state") == "INITIALIZED"
    if config_exists and backend_exists and is_initialized and not overwrite:
        raise AttributeError(
            f"Monitor with name {name} and backend {backend} already exists. Use load_monitor('{name}',"
            f" backend='{backend}') instead."
        )
    backend_ = BACKENDS[backend](params, **kwargs)
    if state == "NOT_INITIALIZED":
        backend_.init_model()
        backend_.dump()
    return backend_


def load_config() -> dict:
    """Loads config from toml file as dict"""
    config_toml = CONFIG_PATH / "config.toml"
    try:
        with open(config_toml) as configfile:
            return toml.load(configfile)
    except FileNotFoundError as e:
        CONFIG_PATH.mkdir(parents=True, exist_ok=True)
        config_toml.touch()
        return {}


def load_monitor(name: str, backend: _backend_types = "ProcessAPI") -> Backend: # TODO: backend sollte mit gedumpt werden
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
        overwrite=True,
        **config[f"{name}"],
        **config[f"{name}.{backend}"],
    )
