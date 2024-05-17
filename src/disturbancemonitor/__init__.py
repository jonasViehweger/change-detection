import datetime
import json
from dataclasses import dataclass, field

import toml

from .backends import CONFIG_PATH, ProcessAPI

BACKENDS = {
    "ProcessAPI": ProcessAPI,
}


def start_monitor(
    name: str,
    monitoring_start: datetime.date,
    geometry: dict,
    resolution: float = 0.001,
    datasource: str = "ARPS",
    harmonics: int = 2,
    inputs: list = ["NDVI"],
    metric: str = "RMSE",
    sensitivity: int = 5,
    boundary: int = 5,
    backend: str = "ProcessAPI",
    state: str = "NOT_INITIALIZED",
    **kwargs,
):
    params = MonitorParameters(
        name=name,
        monitoring_start=monitoring_start,
        geometry=geometry,
        resolution=resolution,
        datasource=datasource,
        harmonics=harmonics,
        inputs=inputs,
        metric=metric,
        sensitivity=sensitivity,
        boundary=boundary,
        state=state,
    )
    Backend = BACKENDS[backend]
    backend = Backend(params, **kwargs)
    if state == "NOT_INITIALIZED":
        backend.init_model()
        backend.dump()
    return backend


def load_monitor(name, backend="ProcessAPI"):
    geom_out = CONFIG_PATH / "geoms"
    with open(CONFIG_PATH / "config.toml", "r") as configfile:
        config = toml.load(configfile)
    with open(geom_out / (name + ".geojson")) as fs:
        geometry = json.load(fs)
    return start_monitor(geometry=geometry, name=name, **config[f"{name}"], **config[f"{name}.{backend}"])


@dataclass
class MonitorParameters:
    name: str
    monitoring_start: datetime.date
    geometry: dict
    resolution: tuple
    datasource: str
    harmonics: int = 2
    inputs: list[str] = field(default_factory=lambda: ["NDVI"])
    metric: str = "RMSE"
    sensitivity: int = 5
    boundary: int = 5
    state: str = "NOT_INITIALIZED"
    last_monitored: datetime.date = None

    def __post_init__(self):
        if self.last_monitored is None:
            self.last_monitored = self.monitoring_start

    @property
    def fit_start(self) -> datetime.date:
        return self.monitoring_start - datetime.timedelta(days=365)


class Monitor:
    pass
    # create
    # name, harmonics, inputs (NDVI?), metric, sensitivity, boundary

    # load
    # name

    # delete
    # name

    # monitor

    # inspect
    # point
