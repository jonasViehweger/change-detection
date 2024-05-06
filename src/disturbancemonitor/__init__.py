import configparser
import json
import os
from contextlib import suppress

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
        self.monitoring_start = monitoring_start
        self.STATUS = "INITIALIZED"
        self.backend = backend

    def dump(self):
        config = configparser.ConfigParser()
        config["DEFAULT"] = {"ServerAliveInterval": "45", "Compression": "yes", "CompressionLevel": "9"}
        config["forge.example"] = {}
        config["forge.example"]["User"] = "hg"
        config["topsecret.server.example"] = {}
        topsecret = config["topsecret.server.example"]
        topsecret["Port"] = "50022"  # mutates the parser
        topsecret["ForwardX11"] = "no"  # same here
        config["DEFAULT"]["ForwardX11"] = "yes"
        with open("example.ini", "w") as configfile:
            config.write(configfile)

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
