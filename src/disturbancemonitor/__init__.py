import configparser
import json
import os
from contextlib import suppress
from pathlib import Path

import toml

from . import backends


class DisturbanceMonitor:
    def __init__(
        self,
        name,
        bucket_name,
        monitoring_start,
        geometry,
        resolution,
        datasource,
        harmonics=2,
        inputs=["NDVI"],
        metric="RMSE",
        sensitivity=5,
        boundary=5,
        status=None,
        backend="AWS",
        **kwargs,
    ):
        if backend == "AWS":
            self.backend = backends.AWSBackend(
                name,
                bucket_name,
                geometry,
                resolution,
                datasource,
                harmonics,
                inputs,
                metric,
                sensitivity,
                boundary,
                **kwargs,
            )
        if status != "INITIALIZED":
            self.backend.create_dataset()
            self.backend.init_model()
            self.status = "INITIALIZED"
        self.name = name
        self.monitoring_start = monitoring_start

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
