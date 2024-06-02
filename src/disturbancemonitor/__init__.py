import datetime
import json
from dataclasses import dataclass, field
from typing import Literal

import toml

from .backends import CONFIG_PATH, AsyncAPI, ProcessAPI
from .monitor_params import MonitorParameters

BACKENDS = {"ProcessAPI": ProcessAPI, "AsyncAPI": AsyncAPI}
_backend_types = Literal["ProcessAPI", "AsyncAPI"]


def start_monitor(
    name: str,
    monitoring_start: datetime.date,
    geometry: dict,
    resolution: float = 0.001,
    datasource: str = "ARPS",
    datasource_id: str | None = None,
    harmonics: int = 2,
    signal: str = "NDVI",
    metric: str = "RMSE",
    sensitivity: int = 5,
    boundary: int = 5,
    backend: _backend_types = "ProcessAPI",
    state: str = "NOT_INITIALIZED",
    overwrite: bool = False,
    **kwargs,
):
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
    )
    config = load_config()
    if name in config and name + "." + backend in config and not overwrite and config[name]["state"] == "INITIALIZED":
        raise AttributeError(
            f"Monitor with name {name} and backend {backend} already exists. Use load_monitor('{name}',"
            f" backend='{backend}') instead."
        )
    backend = BACKENDS[backend](params, **kwargs)
    if state == "NOT_INITIALIZED":
        backend.init_model()
        backend.dump()
    return backend


def load_config():
    with open(CONFIG_PATH / "config.toml") as configfile:
        return toml.load(configfile)


def load_monitor(name, backend: _backend_types = "ProcessAPI"):
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
