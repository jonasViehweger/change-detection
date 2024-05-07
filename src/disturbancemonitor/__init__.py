import configparser
import json
import os
from contextlib import suppress
from pathlib import Path

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
    ):
        backend = backends.AWSBackend(
            name, bucket_name, geometry, resolution, datasource, harmonics, inputs, metric, sensitivity, boundary
        )
        backend.create_dataset()
        backend.init_model()
        self.name = name
        self.monitoring_start = monitoring_start
        self.STATUS = "INITIALIZED"
        self.backend = backend

    def dump(self):
        config = configparser.ConfigParser()
        backend_dict = self.backend.as_dict()
        config[self.name] = {k: v for k, v in self.__dict__.items() if k not in ["backend", "name"]}
        config[self.name + ".backend"] = {k: v for k, v in backend_dict.items() if k not in ["geometry"]}
        out_path = Path().home() / ".config" / "disturbancemonitor"
        geom_out = out_path / "geoms"
        out_path.mkdir(parents=True, exist_ok=True)
        geom_out.mkdir(parents=True, exist_ok=True)
        with open(out_path / "config.ini", "w") as configfile:
            config.write(configfile)
        with open(geom_out / (self.name + ".geojson")) as fs:
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
