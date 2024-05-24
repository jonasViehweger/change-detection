import datetime
import json
import random
import string
from copy import copy
from dataclasses import asdict
from io import BytesIO
from pathlib import Path
from time import sleep

import numpy as np
import rasterio
import toml
from rasterio.session import AWSSession

from .resources import BYOC, S3, ResourceManager, SHClient, ZarrSH

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

    def delete(self):
        """
        Deletes all resources that were created by the monitor
        """
        pass


class ProcessAPI(Backend):
    def __init__(
        self,
        monitor_params,
        zarr_id=None,
        bucket_name=None,
        rollback=True,
        **kwargs,
    ):
        self.random_id = "".join(random.choices(string.ascii_letters + string.digits, k=8))
        self.bucket_name = (bucket_name or monitor_params.name + "-" + self.random_id).lower()
        self.zarr_name = monitor_params.name + ".zarr"
        self.zarr_id = zarr_id
        self.client = SHClient()
        self.s3 = S3(self.bucket_name, self.zarr_name)
        self.zarr = ZarrSH(self.zarr_name, self.bucket_name, self.client, self.zarr_id)
        self.rollback = rollback

        self.url = "https://services.sentinel-hub.com/api/v1/process"
        super().__init__(monitor_params)

    def as_dict(self):
        subset_dict = {
            k: v
            for k, v in self.__dict__.items()
            if k not in ["client", "url", "zarr_name", "monitor_params", "zarr", "s3"]
        }
        return copy(subset_dict)

    def init_model(self):
        with ResourceManager(rollback=self.rollback) as manager:
            print("0/6 Initializing model")
            print("1/6 Creating bucket")
            self.s3.create_bucket(
                policy={
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
            )
            manager.add_resource(self.s3)
            print("2/6 Fitting model")
            models = self.compute_models()
            print("3/6 Writing model to bucket")
            self.s3.write_models(models)
            print("4/6 Ingesting model to SH")
            self.zarr_id = self.zarr.ingest_dataset()
            manager.add_resource(self.zarr)
            print("5/6 Computing metric")
            metrics = self.compute_metric()
            print("6/6 Writing metric to bucket")
            self.s3.write_metric(metrics)
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
                "type": self.monitor_params.datasource_id,
            }
        ]

        beta_request = self.base_request(beta_data, beta_evalscript)
        beta = self.client.post(self.url, json=beta_request)

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
                "type": self.monitor_params.datasource_id,
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

        sigma = self.client.post(self.url, json=sigma_request)
        try:
            sigma.raise_for_status()
        except:
            print(sigma.text)
            raise
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
                "type": self.monitor_params.datasource_id,
                "id": "ARPS",
            },
            {
                "dataFilter": {"timeRange": {"from": "2021-01-01T00:00:00Z", "to": "2022-01-01T00:00:00Z"}},
                "type": f"zarr-{self.zarr_id}",
                "id": "beta",
            },
        ]

        monitor_request = self.base_request(monitor_data, monitor_evalscript)
        monitor_data = self.client.post(self.url, json=monitor_request)
        monitor_data.raise_for_status()

        self.s3.write_monitor(monitor_data.content)
        self.monitor_params.last_monitored = end
        self.dump()

    def delete(self):
        """
        Deletes the S3 Folder for the monitor and the SH Zarr collection
        """
        self.s3.delete()
        self.zarr.delete()
        self.monitor_params.state = "DELETED"
        self.dump()


class AsyncAPI(Backend):
    def __init__(
        self,
        monitor_params,
        bucket_name=None,
        folder_name=None,
        byoc_id=None,
        rollback=True,
        **kwargs,
    ):
        self.random_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        self.bucket_name = bucket_name or (monitor_params.name + "-" + self.random_id).lower()
        self.folder_name = folder_name or (monitor_params.name + "-" + self.random_id).lower()
        self.client = SHClient()
        self.byoc_id = byoc_id
        self.byoc = BYOC(self.bucket_name, self.folder_name, self.client, self.byoc_id)
        self.s3 = S3(self.bucket_name, self.folder_name)
        self.rollback = rollback

        self.url = "https://services.sentinel-hub.com/api/v1/async/process"
        super().__init__(monitor_params)

    def as_dict(self):
        subset_dict = {
            k: v
            for k, v in self.__dict__.items()
            if k not in ["client", "url", "zarr_name", "monitor_params", "zarr", "s3"]
        }
        return copy(subset_dict)

    def init_model(self):
        with ResourceManager(
            rollback=self.rollback,
        ) as manager:
            print("0/6 Initializing model")
            print("1/6 Creating bucket")
            self.s3.create_bucket(
                policy={
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
                        },
                        {
                            "Sid": "Async Permissions",
                            "Effect": "Allow",
                            "Principal": {"AWS": "arn:aws:iam::450268950967:user/jonas"},
                            "Action": ["s3:GetObject", "s3:PutObject"],
                            "Resource": [f"arn:aws:s3:::{self.bucket_name}/*"],
                        },
                    ],
                }
            )
            manager.add_resource(self.s3)
            print("2/6 Fitting model")
            async_id = self.compute_models()
            print("3/6 Writing model to bucket")
            self.write_models(async_id)
            print("4/6 Ingesting model to SH")
            self.byoc_id = self.byoc.create_byoc()
            manager.add_resource(self.byoc)
            self.byoc_id = self.byoc.ingest_tile(self.monitor_params.monitoring_start)
            print("5/6 Computing metric")
            async_id = self.compute_metric()
            print("6/6 Writing metric to bucket")
            self.write_metric(async_id)
            self.monitor_params.state = "INITIALIZED"

    def wait_for_async(self, async_id):
        print("... Waiting for async request to finish")
        while True:
            sleep(5)
            response = self.client.get(url=f"{self.url}/{async_id}")
            if response.status_code == 404:
                # request will be 404 when process finished
                break
                # see if an error was made:
        try:
            with self.s3.s3_out.open(f"s3://{self.bucket_name}/{self.folder_name}/{async_id}/error.json") as fs:
                error = json.load(fs)
                raise RuntimeError(f"Async request failed: {error['message']}")
        except FileNotFoundError:
            pass

        print("... Finished")

    def write_metric(self, async_id):
        s3_root = f"s3://{self.bucket_name}/{self.folder_name}"
        async_out = f"{s3_root}/{async_id}/default.tif"
        with rasterio.Env(AWSSession(session=self.s3.session)):
            with rasterio.open(async_out) as src:
                profile = src.profile
                profile.update(driver="COG", compress="DEFLATE", blockxsize=1024, blockysize=1024, tiled=True)
                with BytesIO() as out:
                    # Create a new file to write to
                    with rasterio.open(out, "w", **profile) as dst:
                        dst.write(src.read())
                    self.s3.write_binary(f"{s3_root}/metric.tif", out)

        # delete non-cog async output
        self.s3.s3_out.delete(f"s3://{self.bucket_name}/{self.folder_name}/{async_id}", recursive=True)

    def write_monitor(self, async_id):
        s3_root = f"s3://{self.bucket_name}/{self.folder_name}"
        async_out = f"{s3_root}/{async_id}/default.tif"
        with rasterio.Env(AWSSession(session=self.s3.session)):
            with rasterio.open(async_out) as src:
                profile = src.profile
                profile.update(driver="COG", compress="DEFLATE", blockxsize=1024, blockysize=1024, tiled=True, count=1)
                with BytesIO() as out:
                    with rasterio.open(out, "w", **profile) as dst:
                        dst.write(src.read(1), 1)
                    self.s3.write_binary(f"{s3_root}/disturbedDate.tif", out)

                with BytesIO() as out:
                    with rasterio.open(out, "w", **profile) as dst:
                        dst.write(src.read(2), 1)
                    self.s3.write_binary(f"{s3_root}/process.tif", out)

        # delete non-cog async output
        self.s3.s3_out.delete(f"s3://{self.bucket_name}/{self.folder_name}/{async_id}", recursive=True)

    def write_models(self, async_id):
        s3_root = f"s3://{self.bucket_name}/{self.folder_name}"
        async_out = f"{s3_root}/{async_id}/default.tif"
        with rasterio.Env(AWSSession(session=self.s3.session)):
            with rasterio.open(async_out) as src:
                profile = src.profile
                profile.update(driver="COG", compress="DEFLATE", blockxsize=1024, blockysize=1024, tiled=True)
                with BytesIO() as out:
                    # Create a new file to write to
                    with rasterio.open(out, "w", **profile) as dst:
                        dst.write(src.read())
                    self.s3.write_binary(f"{s3_root}/c.tif", out)

                # Init all other necessary files (files have only 1 band, init with 0)
                profile.update(count=1)
                zero_raster = np.zeros((profile["height"], profile["width"]), dtype=np.float32)
                with BytesIO() as out:
                    with rasterio.open(out, "w", **profile) as dst:
                        dst.write(zero_raster, 1)
                    self.s3.write_binary(f"{s3_root}/metric.tif", out)
                    self.s3.write_binary(f"{s3_root}/disturbedDate.tif", out)
                    self.s3.write_binary(f"{s3_root}/process.tif", out)

        # delete non-cog async output
        self.s3.s3_out.delete(f"s3://{self.bucket_name}/{self.folder_name}/{async_id}", recursive=True)

    def prepare_evalscript(self, path):
        with open(path, "r") as src:
            evalscript = src.read().split("// DISCARD FROM HERE", 1)[0]
        eval_config = {
            "HARMONICS": self.monitor_params.harmonics,
            "DATASOURCE": self.monitor_params.datasource,
            "INPUT": self.monitor_params.inputs[0],
            "SENSITIVITY": self.monitor_params.sensitivity,
            "BOUND": self.monitor_params.boundary,
        }
        split_config = evalscript.split("// CONFIG")
        split_config[1] = json.dumps(eval_config) + ";"
        return "\n".join(split_config)

    def compute_models(self):
        beta_data = [
            {
                "dataFilter": {
                    "timeRange": {
                        "from": f"{self.monitor_params.fit_start.isoformat()}T00:00:00Z",
                        "to": f"{self.monitor_params.monitoring_start.isoformat()}T00:00:00Z",
                    },
                    "mosaickingOrder": "leastRecent",
                },
                "type": self.monitor_params.datasource_id,
            }
        ]

        beta_request = self.base_request(
            beta_data, 
            self.prepare_evalscript("./evalscripts/beta.cjs")
        )
        beta = self.client.post(self.url, json=beta_request)
        beta.raise_for_status()
        async_id = beta.json()["id"]
        self.wait_for_async(async_id)
        return async_id

    def compute_metric(self):
        sigma_data = [
            {
                "dataFilter": {
                    "timeRange": {
                        "from": f"{self.monitor_params.fit_start.isoformat()}T00:00:00Z",
                        "to": f"{self.monitor_params.monitoring_start.isoformat()}T00:00:00Z",
                    },
                    "mosaickingOrder": "leastRecent",
                },
                "type": self.monitor_params.datasource_id,
                "id": self.monitor_params.datasource,
            },
            {
                "dataFilter": {
                    "timeRange": {
                        "from": f"{self.monitor_params.fit_start.isoformat()}T00:00:00Z",
                        "to": f"{self.monitor_params.monitoring_start.isoformat()}T23:59:59Z",
                    }
                },
                "type": f"byoc-{self.byoc_id}",
                "id": "beta",
            },
        ]

        sigma_request = self.base_request(
            sigma_data, 
            self.prepare_evalscript("./evalscripts/rmse.cjs")
        )
        sigma = self.client.post(self.url, json=sigma_request)
        sigma.raise_for_status()
        async_id = sigma.json()["id"]
        self.wait_for_async(async_id)
        return async_id

    def base_request(self, data: list, evalscript: str):
        crs = "http://www.opengis.net/def/crs/EPSG/0/4326"
        return {
            "input": {"bounds": {"geometry": self.monitor_params.geometry, "properties": {"crs": crs}}, "data": data},
            "output": {
                "resx": self.monitor_params.resolution,
                "resy": self.monitor_params.resolution,
                "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}],
                "delivery": {
                    "s3": {
                        "url": f"s3://{self.bucket_name}/{self.folder_name}",
                        "accessKey": "AKIAWRVQ66G363FBBOML",
                        "secretAccessKey": "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",
                    }
                },
            },
            "evalscript": evalscript,
        }

    def monitor(self, end: datetime.date = datetime.date.today()):
        start = self.monitor_params.last_monitored
        monitor_data = [
            {
                "dataFilter": {
                    "timeRange": {"from": f"{start.isoformat()}T00:00:00Z", "to": f"{end.isoformat()}T23:59:59Z"},
                    "mosaickingOrder": "leastRecent",
                },
                "type": self.monitor_params.datasource_id,
                "id": self.monitor_params.datasource,
            },
            {
                "dataFilter": {"timeRange": {
                    "from": f"{self.monitor_params.monitoring_start.isoformat()}T00:00:00Z", 
                    "to": f"{self.monitor_params.monitoring_start.isoformat()}T23:59:59Z"
                    }},
                "type": f"byoc-{self.byoc_id}",
                "id": "beta",
            },
        ]

        monitor_request = self.base_request(
            monitor_data, 
            self.prepare_evalscript("./evalscripts/predict_ccdc.cjs")
        )
        monitor_data = self.client.post(self.url, json=monitor_request)
        try:
            monitor_data.raise_for_status()
        except:
            print(monitor_data.text)
            raise

        async_id = monitor_data.json()["id"]
        self.wait_for_async(async_id)

        self.write_monitor(async_id)
        self.monitor_params.last_monitored = end
        self.dump()

    def delete(self):
        """
        Deletes the S3 Folder for the monitor and the SH Zarr collection
        """
        self.s3.delete()
        self.monitor_params.state = "DELETED"
        self.byoc.delete()
        self.dump()
