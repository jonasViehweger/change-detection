import json
import os
from contextlib import suppress

import boto3
import s3fs
import xarray as xr
from authlib.integrations.requests_client import OAuth2Session
from rasterio.io import MemoryFile


class DisturbanceMonitor:
    def __init__(
        self,
        name,
        bucket_name,
        monitoring_start,
        geometry,
        res,
        datasource,
        harmonics=2,
        inputs=["NDVI"],
        metric="RMSE",
        sensitivity=5,
        boundary=5,
    ):
        self.name = name
        self.zarr_name = name + ".zarr"
        self.bucket_name = bucket_name
        self.client = OAuth2Session(os.environ["SH_CLIENT_ID"], os.environ["SH_CLIENT_SECRET"])
        self.client.fetch_token("https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token")
        self.timeout = 0
        self.process_api = "https://services.sentinel-hub.com/api/v1/process"
        self.STATUS = "INITIALIZED"

    def fit(
        self,
        name,
        bucket_name,
        monitoring_start,
        geometry,
        res,
        datasource,
        harmonics=2,
        inputs=["NDVI"],
        metric="RMSE",
        sensitivity=5,
        boundary=5,
    ):
        backend = AWSBackend(
            name, bucket_name, geometry, res, datasource, harmonics, inputs, metric, sensitivity, boundary
        )
        backend.create_dataset()
        backend.init_model()

        return cls()

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
