import datetime
import json
import os
import random
import string
from contextlib import suppress
from copy import copy
from dataclasses import asdict
from pathlib import Path
from time import sleep

import boto3
import s3fs
import toml
import xarray as xr
from authlib.integrations.requests_client import OAuth2Session
from rasterio.io import MemoryFile

CONFIG_PATH = Path().home() / ".config" / "disturbancemonitor"


class Backend:
    def __init__(self, monitor_params):
        self.monitor_params = monitor_params
        pass

    def init_model(self):
        raise NotImplementedError

    def monitor(self, end_date=datetime.date.today()):
        """
        Will automatically monitor from `last_monitored` to `end_date`
        """
        raise NotImplementedError

    def as_dict(self):
        raise NotImplementedError

    def dump(self):
        geom_out = CONFIG_PATH / "geoms"
        CONFIG_PATH.mkdir(parents=True, exist_ok=True)
        geom_out.mkdir(parents=True, exist_ok=True)
        toml_path = CONFIG_PATH / "config.toml"

        # Get the saved toml if it already exists:
        if (toml_path).exists():
            with open(toml_path, "r") as configfile:
                config = toml.load(configfile)
        else:
            config = {}

        backend_dict = self.as_dict()
        params_dict = asdict(self.monitor_params)
        name = params_dict.pop("name")
        geometry = params_dict.pop("geometry")

        config.update(
            {
                name: params_dict,
                f"{name}.{type(self).__name__}": backend_dict,
            }
        )
        with open(CONFIG_PATH / "config.toml", "w") as configfile:
            toml.dump(config, configfile)
        with open(geom_out / (name + ".geojson"), "w") as fs:
            json.dump(geometry, fs)


class ProcessAPI(Backend):
    def __init__(
        self,
        monitor_params,
        zarr_id=None,
        bucket_name=None,
        **kwargs,
    ):
        self.random_id = "".join(random.choices(string.ascii_letters + string.digits, k=8))
        self.bucket_name = (bucket_name or monitor_params.name + "-" + self.random_id).lower()
        self.zarr_name = monitor_params.name + ".zarr"
        self.zarr_id = zarr_id
        self.client = OAuth2Session(os.environ["SH_CLIENT_ID"], os.environ["SH_CLIENT_SECRET"])
        self.client.fetch_token("https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token")
        self.process_api = "https://services.sentinel-hub.com/api/v1/process"
        super().__init__(monitor_params)

    def as_dict(self):
        subset_dict = {
            k: v for k, v in self.__dict__.items() if k not in ["client", "process_api", "zarr_name", "monitor_params"]
        }
        return copy(subset_dict)

    def get_token(self):
        if self.client.token.is_expired():
            self.client.fetch_token("https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token")

    def create_bucket(self):
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
                    "Resource": [
                        f"arn:aws:s3:::{self.bucket_name}",
                        f"arn:aws:s3:::{self.bucket_name}/*",
                    ],
                }
            ],
        }

        # Convert the policy from JSON dict to string
        bucket_policy = json.dumps(bucket_policy)

        # Set the new policy
        s3_client.put_bucket_policy(Bucket=self.bucket_name, Policy=bucket_policy)

    def write_models(self, binary):
        with MemoryFile(binary).open() as dataset:
            beta_ds = xr.open_dataset(dataset, band_as_variable=True, engine="rasterio")
        order = ["y", "x"]
        reordered_indexes = {index_name: beta_ds.indexes[index_name] for index_name in order}
        beta_ds = beta_ds.reindex(reordered_indexes)
        beta_ds = beta_ds.rename({col: "c" + col[-1] for col in beta_ds})
        beta_ds["process"] = xr.zeros_like(beta_ds["c1"])
        beta_ds["metric1"] = xr.zeros_like(beta_ds["c1"])
        beta_ds["disturbedDate"] = xr.zeros_like(beta_ds["c1"])

        s3_out = s3fs.S3FileSystem(anon=False, profile="default")
        store_out = s3fs.S3Map(root=f"s3://{self.bucket_name}/{self.zarr_name}", s3=s3_out, check=False)
        beta_ds.to_zarr(store_out, mode="a")

    def write_metric(self, binary):
        with MemoryFile(binary).open() as dataset:
            metrics_ds = xr.open_dataset(dataset, band_as_variable=True, engine="rasterio")
        order = ["y", "x"]
        reordered_indexes = {index_name: metrics_ds.indexes[index_name] for index_name in order}
        metrics_ds = metrics_ds.rename({col: "metric" + col[-1] for col in metrics_ds})
        metrics_ds = metrics_ds.reindex(reordered_indexes)

        s3_out = s3fs.S3FileSystem(anon=False, profile="default")
        store_out = s3fs.S3Map(root=f"s3://{self.bucket_name}/{self.zarr_name}", s3=s3_out, check=False)
        metrics_ds.to_zarr(store_out, mode="a")

    def write_monitor(self, binary):
        with MemoryFile(binary).open() as dataset:
            metrics_ds = xr.open_dataset(dataset, band_as_variable=True, engine="rasterio")
        order = ["y", "x"]
        reordered_indexes = {index_name: metrics_ds.indexes[index_name] for index_name in order}
        rename = ["disturbedDate", "process"]
        metrics_ds = metrics_ds.rename({col: new_name for col, new_name in zip(metrics_ds, rename)})
        metrics_ds = metrics_ds.reindex(reordered_indexes)

        s3_out = s3fs.S3FileSystem(anon=False, profile="default")
        store_out = s3fs.S3Map(root=f"s3://{self.bucket_name}/{self.zarr_name}", s3=s3_out, check=False)
        metrics_ds.to_zarr(store_out, mode="a")

    def ingest_dataset(self):
        # Make new Zarr storage on SH
        zarr_api = "https://services.sentinel-hub.com/api/v1/zarr/collections"
        zarr_data = {
            "name": self.monitor_params.name,
            "s3Bucket": self.bucket_name,
            "path": f"{self.zarr_name}/",
            "crs": "http://www.opengis.net/def/crs/EPSG/0/4326",
        }
        zarr_byoc = self.client.post(zarr_api, json=zarr_data)
        zarr_byoc.raise_for_status()
        self.zarr_id = zarr_byoc.json()["data"]["id"]

        print("Waiting for collection to finish ingestion")
        # wait for zarr collection to fully ingest
        while True:
            sleep(5)
            zarr_coll = self.client.get(f"{zarr_api}/{self.zarr_id}").json()
            if zarr_coll["data"]["status"] == "INGESTED":
                break
        print("Ingested")

    def init_model(self):
        print("0/6 Initializing model")
        print("1/6 Creating bucket")
        self.create_bucket()
        print("2/6 Fitting model")
        models = self.compute_models()
        print("3/6 Writing model to bucket")
        self.write_models(models)
        print("4/6 Ingesting model to SH")
        self.ingest_dataset()
        print("5/6 Computing metric")
        metrics = self.compute_metric()
        print("6/6 Writing metric to bucket")
        self.write_metric(metrics)
        self.monitor_params.state = "INITIALIZED"

    def compute_models(self):
        with open("./evalscripts/beta.cjs", "r") as src:
            beta_evalscript = src.read().split("// DISCARD FROM HERE", 1)[0]

        beta_data = [
            {
                "dataFilter": {
                    "timeRange": {
                        "from": f"{self.monitor_params.fit_start.isoformat()}T00:00:00Z",
                        "to": f"{self.monitor_params.monitoring_start.isoformat()}T00:00:00Z",
                    },
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
        with open("./evalscripts/rmse.cjs", "r") as src:
            sigma_evalscript = src.read()

        sigma_data = [
            {
                "dataFilter": {
                    "timeRange": {
                        "from": f"{self.monitor_params.fit_start.isoformat()}T00:00:00Z",
                        "to": f"{self.monitor_params.monitoring_start.isoformat()}T00:00:00Z",
                    },
                    "mosaickingOrder": "leastRecent",
                },
                "type": "byoc-b690a8ba-05c4-49dc-91c7-8484a1007176",
                "id": "ARPS",
            },
            {
                "dataFilter": {
                    "timeRange": {
                        "from": f"{self.monitor_params.fit_start.isoformat()}T00:00:00Z",
                        "to": f"{self.monitor_params.monitoring_start.isoformat()}T00:00:00Z",
                    }
                },
                "type": f"zarr-{self.zarr_id}",
                "id": "beta",
            },
        ]

        sigma_request = self.base_request(sigma_data, sigma_evalscript)

        sigma = self.client.post("https://services.sentinel-hub.com/api/v1/process", json=sigma_request)
        sigma.raise_for_status()
        return sigma.content

    def base_request(self, data: list, evalscript: str):
        crs = "http://www.opengis.net/def/crs/EPSG/0/4326"
        return {
            "input": {"bounds": {"geometry": self.monitor_params.geometry, "properties": {"crs": crs}}, "data": data},
            "output": {
                "resx": self.monitor_params.resolution,
                "resy": self.monitor_params.resolution,
                "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}],
            },
            "evalscript": evalscript,
        }

    def monitor(self, end: datetime.date = datetime.date.today()):
        start = self.monitor_params.last_monitored

        with open("./evalscripts/predict_ccdc.cjs", "r") as src:
            monitor_evalscript = src.read().split("// DISCARD FROM HERE", 1)[0]

        monitor_data = [
            {
                "dataFilter": {
                    "timeRange": {"from": f"{start.isoformat()}T00:00:00Z", "to": f"{end.isoformat()}T23:59:59Z"},
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

        monitor_request = self.base_request(monitor_data, monitor_evalscript)
        monitor_data = self.client.post(self.process_api, json=monitor_request)
        monitor_data.raise_for_status()

        self.write_monitor(monitor_data.content)
        self.monitor_params.last_monitored = end
        self.dump()
