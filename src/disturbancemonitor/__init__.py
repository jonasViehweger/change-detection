import datetime
import json
from dataclasses import dataclass, field
from typing import Optional

import toml

from .backends import CONFIG_PATH, AsyncAPI, ProcessAPI

BACKENDS = {"ProcessAPI": ProcessAPI, "AsyncAPI": AsyncAPI}


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
    backend: str = "ProcessAPI",
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


def load_monitor(name, backend="ProcessAPI"):
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


datasource_ids = {"S2L2A": "sentinel-2-l2a"}


@dataclass
class MonitorParameters:
    name: str
    monitoring_start: datetime.date
    geometry: dict
    resolution: tuple
    datasource: str
    datasource_id: str = None
    harmonics: int = 2
    signal: str = "NDVI"
    metric: str = "RMSE"
    sensitivity: int = 5
    boundary: int = 5
    state: str = "NOT_INITIALIZED"
    last_monitored: datetime.date = None

    def __post_init__(self):
        if self.last_monitored is None:
            self.last_monitored = self.monitoring_start
        if self.datasource_id is None:
            self.datasource_id = datasource_ids[self.datasource]

    @property
    def fit_start(self) -> datetime.date:
        return self.monitoring_start - datetime.timedelta(days=365)
