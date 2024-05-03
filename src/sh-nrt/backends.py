import json
import os
from contextlib import suppress

import boto3
import s3fs
import xarray as xr
from authlib.integrations.requests_client import OAuth2Session
from rasterio.io import MemoryFile


class BackendInterface:
    def __init__(self):
        pass

    def create_dataset(self, models, metrics):
        raise NotImplementedError("Subclasses must implement create method")

    def write_dataset(self, models, metrics):
        raise NotImplementedError("Subclasses must implement write_dataset method")


class AWSBackend(BackendInterface):
    def __init__(self, name, bucket_name):
        self.name = name
        self.zarr_name = name + ".zarr"
        self.bucket_name = bucket_name
        self.client = OAuth2Session(os.environ["SH_CLIENT_ID"], os.environ["SH_CLIENT_SECRET"])
        self.client.fetch_token("https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token")
        self.timeout = 0
        self.process_api = "https://services.sentinel-hub.com/api/v1/process"

    def get_token(self):
        if self.client.token.is_expired():
            self.client.fetch_token("https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token")

    def create_dataset(self):
        boto3.setup_default_session(profile_name="default")
        s3_client = boto3.client("s3", region_name="eu-central-1")
        location = {"LocationConstraint": "eu-central-1"}
        with suppress(s3_client.exceptions.BucketAlreadyOwnedByYou):
            s3_client.create_bucket(Bucket=self.bucket_name, CreateBucketConfiguration=location)

        # Set SH BYOC bucket policy
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "Sentinel Hub permissions",
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::614251495211:root"},
                    "Action": ["s3:GetBucketLocation", "s3:ListBucket", "s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{self.bucket_name}", f"arn:aws:s3:::{self.bucket_name}/*"],
                }
            ],
        }

        # Convert the policy from JSON dict to string
        bucket_policy = json.dumps(bucket_policy)

        # Set the new policy
        s3_client.put_bucket_policy(Bucket=self.bucket_name, Policy=bucket_policy)

    def write_dataset(self, models, metrics):
        with MemoryFile(models).open() as dataset:
            beta_ds = xr.open_dataset(dataset, band_as_variable=True, engine="rasterio")
        order = ["y", "x"]
        reordered_indexes = {index_name: beta_ds.indexes[index_name] for index_name in order}
        beta_ds = beta_ds.reindex(reordered_indexes)
        beta_ds = beta_ds.rename({col: "c" + col[-1] for col in beta_ds})
        beta_ds["process"] = xr.zeros_like(beta_ds["c1"])
        s3_out = s3fs.S3FileSystem(anon=False, profile="default")
        store_out = s3fs.S3Map(root=f"s3://{self.bucket_name}/{self.zarr_name}", s3=s3_out, check=False)
        beta_ds.to_zarr(store_out, mode="a")

        with MemoryFile(metrics).open() as dataset:
            metrics_ds = xr.open_dataset(dataset, band_as_variable=True, engine="rasterio")
        order = ["y", "x"]
        reordered_indexes = {index_name: metrics_ds.indexes[index_name] for index_name in order}
        metrics_ds = metrics_ds.rename({col: "metric" + col[-1] for col in metrics_ds})
        metrics_ds.to_zarr(store_out, mode="a")

        # Make new Zarr storage on SH
        zarr_api = "https://services.sentinel-hub.com/api/v1/zarr/collections"
        zarr_data = {
            "name": self.name,
            "s3Bucket": self.bucket_name,
            "path": f"{self.zarr_name}/",
            "crs": "http://www.opengis.net/def/crs/EPSG/0/4326",
        }
        zarr_byoc = self.client.post(zarr_api, json=zarr_data)
        zarr_byoc.raise_for_status()
        self.zarr_id = zarr_byoc.json()["data"]["id"]

    def init_model(self):
        models = self.compute_models()
        metrics = self.compute_metric()
        return models, metrics

    def compute_models(self):
        with open("../evalscripts/beta.cjs", "r") as src:
            beta_evalscript = src.read().split("// DISCARD FROM HERE", 1)[0]

        beta_data = [
            {
                "dataFilter": {
                    "timeRange": {"from": "2021-01-01T00:00:00Z", "to": "2022-01-01T00:00:00Z"},
                    "mosaickingOrder": "leastRecent",
                },
                "type": "byoc-b690a8ba-05c4-49dc-91c7-8484a1007176",
            }
        ]

        beta_request = self.base_request(beta_data, beta_evalscript)
        beta = self.client.post("https://services.sentinel-hub.com/api/v1/process", json=beta_request)

        beta.raise_for_status()
        return beta.content

    def compute_metric(self):
        with open("../evalscripts/rmse.cjs", "r") as src:
            sigma_evalscript = src.read()

        sigma_data = [
            {
                "dataFilter": {
                    "timeRange": {"from": "2021-01-01T00:00:00Z", "to": "2022-01-01T00:00:00Z"},
                    "mosaickingOrder": "leastRecent",
                },
                "type": "byoc-b690a8ba-05c4-49dc-91c7-8484a1007176",
                "id": "ARPS",
            },
            {
                "dataFilter": {"timeRange": {"from": "2021-01-01T00:00:00Z", "to": "2022-01-01T00:00:00Z"}},
                "type": f"zarr-{self.zarr_id}",
                "id": "beta",
            },
        ]

        sigma_request = self.base_request(sigma_data, sigma_evalscript)

        sigma = self.client.post("https://services.sentinel-hub.com/api/v1/process", json=sigma_request)
        sigma.raise_for_status()
        return sigma.content

    def base_request(self, data: list, evalscript: str):
        res = 5  # meters

        aoi = [696920, 4528660, 700140, 4532020]
        crs = "http://www.opengis.net/def/crs/EPSG/0/32614"
        return {
            "input": {"bounds": {"bbox": aoi, "properties": {"crs": crs}}, "data": data},
            "output": {
                "resx": res,
                "resy": res,
                "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}],
            },
            "evalscript": evalscript,
        }
