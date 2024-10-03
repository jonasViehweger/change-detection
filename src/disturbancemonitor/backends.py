import datetime
import json
import random
import string
import tarfile
from collections.abc import Callable
from copy import copy
from dataclasses import asdict
from importlib.resources import files
from importlib.resources.abc import Traversable
from io import BytesIO
from pathlib import Path
from time import sleep

import boto3
import rasterio
import toml
from rasterio.io import MemoryFile
from rasterio.session import AWSSession

from .cog import write_metric, write_models, write_monitor
from .monitor_params import MonitorParameters
from .resources import BYOC, S3, ResourceManager, SHClient, SHConfiguration

CONFIG_PATH = Path().home() / ".config" / "disturbancemonitor"
DATA_PATH = files("disturbancemonitor.data")


class Backend:
    def __init__(self, monitor_params: MonitorParameters) -> None:
        self.monitor_params = monitor_params

    def init_model(self) -> None:
        raise NotImplementedError

    def monitor(self, end: datetime.date | None = None) -> None:
        """
        Will automatically monitor from `last_monitored` to `end_date`
        """
        raise NotImplementedError

    def as_dict(self) -> dict:
        raise NotImplementedError

    def dump(self) -> None:
        geom_out = CONFIG_PATH / "geoms"
        CONFIG_PATH.mkdir(parents=True, exist_ok=True)
        geom_out.mkdir(parents=True, exist_ok=True)
        toml_path = CONFIG_PATH / "config.toml"

        # Get the saved toml if it already exists:
        if (toml_path).exists():
            with open(toml_path) as configfile:
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

    def delete(self) -> None:
        """
        Deletes all resources that were created by the monitor
        """
        raise NotImplementedError


def prepare_evalscript(monitor_params: MonitorParameters, path: Path | Traversable) -> str:
    with path.open() as src:
        evalscript = src.read().split("// DISCARD FROM HERE", 1)[0]
    eval_config = {
        "HARMONICS": monitor_params.harmonics,
        "DATASOURCE": monitor_params.datasource,
        "INPUT": monitor_params.signal,
        "SENSITIVITY": monitor_params.sensitivity,
        "BOUND": monitor_params.boundary,
    }
    split_config = evalscript.split("// CONFIG")
    split_config[1] = json.dumps(eval_config) + ";"
    return "\n".join(split_config)


class ProcessAPI(Backend):
    def __init__(
        self,
        monitor_params: MonitorParameters,
        byoc_id: str | None = None,
        s3_profile: str = "default",
        sh_profile: str = "default-profile",
        bucket_name: str | None = None,
        folder_name: str | None = None,
        rollback: bool = True,
    ) -> None:
        self.random_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        self.bucket_name = bucket_name or (monitor_params.name + "-" + self.random_id).lower()
        self.folder_name = folder_name or (monitor_params.name).lower()
        self.s3_profile = s3_profile
        self.sh_profile = sh_profile
        self.client = SHClient(self.sh_profile)
        self.byoc_id = byoc_id
        self.byoc = BYOC(self.bucket_name, self.folder_name, self.client, self.byoc_id)
        self.s3 = S3(self.bucket_name, self.folder_name, self.s3_profile)
        self.rollback = rollback

        self.url = "https://services.sentinel-hub.com/api/v1/process"
        super().__init__(monitor_params)

    def as_dict(self) -> dict:
        subset_dict = {
            k: v for k, v in self.__dict__.items() if k not in ["client", "url", "monitor_params", "byoc", "s3"]
        }
        return copy(subset_dict)

    def init_model(self) -> None:
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
                            "Action": [
                                "s3:GetBucketLocation",
                                "s3:ListBucket",
                                "s3:GetObject",
                            ],
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
            with MemoryFile(models) as memfile:
                write_models(memfile, self.s3)
            print("4/6 Ingesting model to SH")
            self.byoc_id = self.byoc.create_byoc()
            manager.add_resource(self.byoc)
            self.byoc.ingest_tile(self.monitor_params.monitoring_start)
            print("5/6 Creating configuration")
            self.sh_configuration = SHConfiguration(self.client, self.monitor_params.name, self.byoc_id)
            manager.add_resource(self.sh_configuration)
            self.sh_configuration.create_instance()
            print("6/6 Creating layer")
            with DATA_PATH.joinpath("visualize_disturbed_date.cjs").open() as src:
                evalscript = src.read()
            self.sh_configuration.create_layer("DISTURBED-DATE", evalscript)
            print("5/6 Computing metric")
            metrics = self.compute_metric()
            print("6/6 Writing metric to bucket")
            with MemoryFile(metrics) as memfile:
                write_metric(memfile, self.s3)
            self.monitor_params.state = "INITIALIZED"

    def compute_models(self) -> bytes:
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
            prepare_evalscript(self.monitor_params, DATA_PATH.joinpath("beta.cjs")),
        )
        beta = self.client.post(self.url, json=beta_request)

        try:
            beta.raise_for_status()
        except:
            print(beta.content)
            raise
        return beta.content

    def compute_metric(self) -> bytes:
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
            prepare_evalscript(self.monitor_params, DATA_PATH.joinpath("rmse.cjs")),
        )

        sigma = self.client.post(self.url, json=sigma_request)
        try:
            sigma.raise_for_status()
        except:
            print(sigma.text)
            raise
        return sigma.content

    def base_request(self, data: list, evalscript: str) -> dict:
        crs = "http://www.opengis.net/def/crs/EPSG/0/4326"
        return {
            "input": {
                "bounds": {
                    "geometry": self.monitor_params.geometry,
                    "properties": {"crs": crs},
                },
                "data": data,
            },
            "output": {
                "resx": self.monitor_params.resolution,
                "resy": self.monitor_params.resolution,
                "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}],
            },
            "evalscript": evalscript,
        }

    def monitor(self, end: datetime.date | None = None) -> dict:
        if end is None:
            end = datetime.date.today()
        start = self.monitor_params.last_monitored
        monitor_data_json = [
            {
                "dataFilter": {
                    "timeRange": {
                        "from": f"{start.isoformat()}T00:00:00Z",
                        "to": f"{end.isoformat()}T23:59:59Z",
                    },
                    "mosaickingOrder": "leastRecent",
                },
                "type": self.monitor_params.datasource_id,
                "id": self.monitor_params.datasource,
            },
            {
                "dataFilter": {
                    "timeRange": {
                        "from": f"{self.monitor_params.monitoring_start.isoformat()}T00:00:00Z",
                        "to": f"{self.monitor_params.monitoring_start.isoformat()}T23:59:59Z",
                    }
                },
                "type": f"byoc-{self.byoc_id}",
                "id": "beta",
            },
        ]

        monitor_request = self.base_request(
            monitor_data_json,
            prepare_evalscript(self.monitor_params, DATA_PATH.joinpath("predict.cjs")),
        )
        # Get userdata (returns number of disturbed pixels during the monitoring)
        monitor_request["output"]["responses"].append(
            {"identifier": "userdata", "format": {"type": "application/json"}}
        )
        monitor_data = self.client.post(self.url, json=monitor_request, headers={"Accept": "application/tar"})
        try:
            monitor_data.raise_for_status()
        except:
            print(monitor_data.content)
            raise

        with tarfile.open(fileobj=BytesIO(monitor_data.content)) as tar:
            # Find the userdata.json file
            userdata_file = tar.extractfile("userdata.json")  # Extract it in memory
            # Read the content of userdata.json
            json_data = userdata_file.read().decode("utf-8")  # Decode from bytes to string

            # Parse the JSON string into a dictionary
            userdata_dict = json.loads(json_data)

            # Find the userdata.json file
            output_tif = tar.extractfile("default.tif")  # Extract it in memory
            # Read the content of userdata.json
            with MemoryFile(output_tif.read()) as memfile:
                write_monitor(memfile, self.s3)

        self.monitor_params.last_monitored = end
        self.dump()
        return userdata_dict

    def delete(self) -> None:
        """
        Deletes the S3 Folder for the monitor and the SH BYOC collection
        """
        self.s3.delete()
        self.byoc.delete()
        self.monitor_params.state = "DELETED"
        self.dump()


class AsyncAPI(Backend):
    def __init__(
        self,
        monitor_params: MonitorParameters,
        bucket_name: str | None = None,
        folder_name: str | None = None,
        byoc_id: str | None = None,
        sh_profile: str = "default-profile",
        s3_profile: str = "default",
        async_profile: str | None = None,
        role_arn: str | None = None,
        rollback: bool = True,
    ) -> None:
        self.random_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        self.bucket_name = bucket_name or (monitor_params.name + "-" + self.random_id).lower()
        self.folder_name = folder_name or (monitor_params.name).lower()
        self.s3_profile = s3_profile
        self.sh_profile = sh_profile
        self.client = SHClient(self.sh_profile)
        self.byoc_id = byoc_id
        self.byoc = BYOC(self.bucket_name, self.folder_name, self.client, self.byoc_id)
        self.s3 = S3(self.bucket_name, self.folder_name, self.s3_profile)
        self.async_profile = async_profile
        self.role_arn = role_arn
        self.rollback = rollback

        self.url = "https://services.sentinel-hub.com/api/v1/async/process"
        super().__init__(monitor_params)

    def as_dict(self) -> dict:
        subset_dict = {
            k: v for k, v in self.__dict__.items() if k not in ["client", "url", "monitor_params", "byoc", "s3"]
        }
        return copy(subset_dict)

    def init_model(self) -> None:
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
                            "Action": [
                                "s3:GetBucketLocation",
                                "s3:ListBucket",
                                "s3:GetObject",
                            ],
                            "Resource": [
                                f"arn:aws:s3:::{self.bucket_name}",
                                f"arn:aws:s3:::{self.bucket_name}/*",
                            ],
                        },
                        {
                            "Sid": "Async Permissions",
                            "Effect": "Allow",
                            "Principal": {"AWS": self.role_arn},
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
            self.write_async(async_id, write_models)
            print("4/6 Ingesting model to SH")
            self.byoc_id = self.byoc.create_byoc()
            manager.add_resource(self.byoc)
            self.byoc.ingest_tile(self.monitor_params.monitoring_start)
            print("5/6 Computing metric")
            async_id = self.compute_metric()
            print("6/6 Writing metric to bucket")
            self.write_async(async_id, write_metric)
            self.monitor_params.state = "INITIALIZED"

    def wait_for_async(self, async_id: str) -> None:
        print("... Waiting for async request to finish")
        while True:
            sleep(5)
            response = self.client.get(url=f"{self.url}/{async_id}")
            if response.status_code == 404:
                # request will be 404 when process finished
                break
                # see if an error was made:
        try:
            with self.s3.s3fs.open(f"s3://{self.bucket_name}/{self.folder_name}/{async_id}/error.json") as fs:
                error = json.load(fs)
                raise RuntimeError(f"Async request failed: {error['message']}")
        except FileNotFoundError:
            pass

        print("... Finished")

    def write_async(self, async_id: str, write_function: Callable[[str, S3], None]) -> None:
        async_out = f"{self.s3.root}/{async_id}/default.tif"
        with rasterio.Env(AWSSession(session=self.s3.session)):
            write_function(async_out, self.s3)

        # delete non-cog async output
        self.s3.s3fs.delete(f"{self.s3.root}/{async_id}", recursive=True)

    def compute_models(self) -> str:
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
            prepare_evalscript(self.monitor_params, DATA_PATH.joinpath("beta.cjs")),
        )
        beta = self.client.post(self.url, json=beta_request)
        beta.raise_for_status()
        async_id = beta.json()["id"]
        self.wait_for_async(async_id)
        return async_id

    def compute_metric(self) -> str:
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
            prepare_evalscript(self.monitor_params, DATA_PATH.joinpath("rmse.cjs")),
        )
        sigma = self.client.post(self.url, json=sigma_request)
        sigma.raise_for_status()
        async_id = sigma.json()["id"]
        self.wait_for_async(async_id)
        return async_id

    def base_request(self, data: list, evalscript: str) -> dict:
        crs = "http://www.opengis.net/def/crs/EPSG/0/4326"
        credentials = boto3.session.Session(profile_name=self.async_profile).get_credentials()
        assert credentials is not None
        return {
            "input": {
                "bounds": {
                    "geometry": self.monitor_params.geometry,
                    "properties": {"crs": crs},
                },
                "data": data,
            },
            "output": {
                "resx": self.monitor_params.resolution,
                "resy": self.monitor_params.resolution,
                "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}],
                "delivery": {
                    "s3": {
                        "url": f"s3://{self.bucket_name}/{self.folder_name}",
                        "accessKey": credentials.access_key,
                        "secretAccessKey": credentials.secret_key,
                    }
                },
            },
            "evalscript": evalscript,
        }

    def monitor(self, end: datetime.date | None = None) -> None:
        if end is None:
            end = datetime.date.today()
        start = self.monitor_params.last_monitored
        monitor_data_json = [
            {
                "dataFilter": {
                    "timeRange": {
                        "from": f"{start.isoformat()}T00:00:00Z",
                        "to": f"{end.isoformat()}T23:59:59Z",
                    },
                    "mosaickingOrder": "leastRecent",
                },
                "type": self.monitor_params.datasource_id,
                "id": self.monitor_params.datasource,
            },
            {
                "dataFilter": {
                    "timeRange": {
                        "from": f"{self.monitor_params.monitoring_start.isoformat()}T00:00:00Z",
                        "to": f"{self.monitor_params.monitoring_start.isoformat()}T23:59:59Z",
                    }
                },
                "type": f"byoc-{self.byoc_id}",
                "id": "beta",
            },
        ]

        monitor_request = self.base_request(
            monitor_data_json,
            prepare_evalscript(self.monitor_params, DATA_PATH.joinpath("predict.cjs")),
        )
        monitor_data = self.client.post(self.url, json=monitor_request)
        try:
            monitor_data.raise_for_status()
        except:
            print(monitor_data.text)
            raise

        async_id = monitor_data.json()["id"]
        self.wait_for_async(async_id)

        self.write_async(async_id, write_monitor)
        self.monitor_params.last_monitored = end
        self.dump()

    def delete(self) -> None:
        """
        Deletes the S3 Folder for the monitor and the SH BYOC collection
        """
        self.s3.delete()
        self.monitor_params.state = "DELETED"
        self.byoc.delete()
        self.dump()
