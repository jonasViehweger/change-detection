import json
from dataclasses import dataclass, field

import toml

from .backends import CONFIG_PATH, ProcessAPI

BACKENDS = {
    "ProcessAPI": ProcessAPI,
}


def start_monitor(
    name: str,
    monitoring_start: str,
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
        name,
        monitoring_start,
        geometry,
        resolution,
        datasource,
        harmonics,
        inputs,
        metric,
        sensitivity,
        boundary,
        state,
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
    monitoring_start: str
    geometry: dict
    resolution: tuple
    datasource: str
    harmonics: int = 2
    inputs: list[str] = field(default_factory=lambda: ["NDVI"])
    metric: str = "RMSE"
    sensitivity: int = 5
    boundary: int = 5
    state: str = "NOT_INITIALIZED"

    @classmethod
    def from_config(cls, name):
        pass


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
