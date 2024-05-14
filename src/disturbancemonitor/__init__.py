import configparser
import json
import os
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

import toml

from .backends import ProcessAPI


@dataclass
class MonitorParameters:
    monitoring_start: str
    geometry: dict
    resolution: tuple
    datasource: str
    harmonics: int = 2
    inputs: list = ["NDVI"]
    metric: str = "RMSE"
    sensitivity: int = 5
    boundary: int = 5


class Monitor:
    def __init__(
        self,
        name,
        monitor,
        backend="ProcessAPI",
        status=None,
        **kwargs,
    ):
        self.name = name
        backends = {"ProcessAPI": ProcessAPI}
        self.backend = backends[backend](name, monitor, **kwargs)
        if status != "INITIALIZED":
            self.backend.create_dataset()
            self.backend.init_model()
            self.status = "INITIALIZED"
        self.backend = backend

    @classmethod
    def load(cls, name):
        out_path = Path().home() / ".config" / "disturbancemonitor"
        geom_out = out_path / "geoms"
        with open(out_path / "config.toml", "r") as configfile:
            config = toml.load(configfile)
        with open(geom_out / (name + ".geojson")) as fs:
            geometry = json.load(fs)
        return cls(geometry=geometry, **config[f"{name}.backend"], **config[f"{name}"])

    def dump(self):
        out_path = Path().home() / ".config" / "disturbancemonitor"
        geom_out = out_path / "geoms"
        out_path.mkdir(parents=True, exist_ok=True)
        geom_out.mkdir(parents=True, exist_ok=True)
        toml_path = out_path / "config.toml"

        # Get the saved toml if it already exists:
        if (toml_path).exists():
            with open(toml_path, "r") as configfile:
                config = toml.load(configfile)
        else:
            config = {}

        backend_dict = self.backend.as_dict()
        config.update(
            {
                self.name: {k: v for k, v in self.__dict__.items() if k not in ["backend", "name"]},
                self.name + ".backend": {k: v for k, v in backend_dict.items() if k not in ["geometry"]},
            }
        )
        with open(out_path / "config.toml", "w") as configfile:
            toml.dump(config, configfile)
        with open(geom_out / (self.name + ".geojson"), "w") as fs:
            json.dump(backend_dict["geometry"], fs)

    def monitor(self):
        self.storage.get()

    # create
    # name, harmonics, inputs (NDVI?), metric, sensitivity, boundary

    # load
    # name

    # delete
    # name

    # monitor

    # inspect
    # point


def DisturbanceMonitor(self, species, sub_species, length, weight, is_salt_water=False):
    mapper = {True: backends.ProcessAPI}
    monitor = Monitor(species, sub_species, length, weight)
    return mapper[is_salt_water](monitor)
