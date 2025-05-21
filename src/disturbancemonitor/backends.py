import datetime
import json
import random
import string
import tarfile
from copy import copy
from importlib.resources.abc import Traversable
from io import BytesIO
from pathlib import Path

import rasterio
from rasterio.io import MemoryFile
import numpy as np

from .cog import write_metric, write_models, write_monitor
from .constants import DATA_PATH, FEATURE_ID_COLUMN, Endpoints
from .db import (
    save_backend_config,
    save_monitor_params,
    update_monitor_state,
)
from .geo_config_handler import geo_config
from .monitor_params import MonitorParameters
from .resources import BYOC, S3, ResourceManager, SHClient, SHConfiguration


class Backend:
    def __init__(self, monitor_params: MonitorParameters) -> None:
        self.monitor_params = monitor_params

    def init_model(self) -> None:
        raise NotImplementedError

    def monitor(self, end: datetime.date | None = None) -> dict | None:
        """
        Will automatically monitor from `last_monitored` to `end_date`
        """
        raise NotImplementedError

    def as_dict(self) -> dict:
        raise NotImplementedError

    def dump(self) -> None:
        """
        Save backend configuration and monitor parameters to the database.
        """
        backend_dict = self.as_dict()
        backend_type = type(self).__name__

        # Save monitor parameters
        save_monitor_params(self.monitor_params)

        # Save backend configuration
        save_backend_config(self.monitor_params.name, backend_type, backend_dict)

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
        bucket_name: str | None = None,
        folder_name: str | None = None,
        byoc_id: str | None = None,
        instance_id: str | None = None,
        s3_profile: str | None = None,
        sh_profile: str = "default-profile",
        monitor_id: str | None = None,
        rollback: bool = True,
    ) -> None:
        self.urls = Endpoints[monitor_params.endpoint].value
        self.url = self.urls.base_url + "/api/v1/process"

        self.monitor_id = monitor_id or "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        self.bucket_name = bucket_name or (monitor_params.name + "-" + self.monitor_id).lower()
        self.folder_name = folder_name or (monitor_params.name).lower()
        self.s3_profile = s3_profile
        self.sh_profile = sh_profile
        self.client = SHClient(self.urls.auth_url, self.sh_profile)
        self.byoc_id = byoc_id
        self.instance_id = instance_id
        self.byoc = BYOC(self.urls.base_url, self.bucket_name, self.folder_name, self.client, self.byoc_id)
        self.s3 = S3(self.bucket_name, self.folder_name, self.s3_profile)
        self.sh_configuration = SHConfiguration(self.urls.base_url, self.client, monitor_params.name, self.instance_id)
        self.rollback = rollback

        # Load geometries from GeoPackage instead of direct file
        self.geometries = geo_config.load_geometry(monitor_params.geometry_path)

        super().__init__(monitor_params)

    def as_dict(self) -> dict:
        subset_dict = {
            k: v
            for k, v in self.__dict__.items()
            if k not in ["client", "url", "urls", "monitor_params", "byoc", "s3", "sh_configuration", "geometries"]
        }
        return copy(subset_dict)

    def init_model(self) -> None:
        update_monitor_state(self.monitor_params.name, "INITIALIZING")
        self.monitor_params.state = "INITIALIZING"
        self.dump()
        with ResourceManager(rollback=self.rollback) as manager:
            print("0/6 Initializing model")
            print("1/6 Creating bucket")
            self.s3.create_bucket(self.urls.bucket_location)
            self.s3.update_policy(
                new_statements=[
                    {
                        "Sid": "Disturbance Monitor BYOC Permissions",
                        "Effect": "Allow",
                        "Principal": {"AWS": self.urls.byoc_principal},
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
                ]
            )
            manager.add_resource(self.s3)
            print("2/6 BYOC")
            self.byoc_id = self.byoc.create_byoc()
            manager.add_resource(self.byoc)
            for feature in self.geometries.iterfeatures():
                feature_id = feature["properties"][FEATURE_ID_COLUMN]
                geometry = feature["geometry"]
                print("2/6 Fitting model")
                models = self.compute_models(geometry)
                print("3/6 Writing model to bucket")
                with MemoryFile(models) as memfile:
                    write_models(memfile, self.s3, feature_id)
                print("4/6 Ingesting model to SH")
                self.byoc.ingest_tile(self.monitor_params.monitoring_start, feature_id)
                print("5/6 Computing metric")
                metrics = self.compute_metric(geometry)
                print("6/6 Writing metric to bucket")
                with MemoryFile(metrics) as memfile:
                    with rasterio.open(memfile) as src:
                        array = src.read()
                        monitored_pixels = np.count_nonzero(~np.isnan(array))
                        geo_config.update_monitored_pixels(self.monitor_id, feature_id, monitored_pixels)
                    write_metric(memfile, self.s3, feature_id)
            print("5/6 Creating configuration")
            manager.add_resource(self.sh_configuration)
            self.instance_id = self.sh_configuration.create_instance()
            print("6/6 Creating layer")
            with DATA_PATH.joinpath("visualize_disturbed_date.cjs").open() as src:
                evalscript = src.read()
            self.sh_configuration.create_layer("DISTURBED-DATE", evalscript, self.byoc_id)
            self.monitor_params.state = "INITIALIZED"
            update_monitor_state(self.monitor_params.name, "INITIALIZED")
            self.dump()

    def compute_models(self, geometry: dict) -> bytes:
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
            beta_data, prepare_evalscript(self.monitor_params, DATA_PATH.joinpath("beta.cjs")), geometry
        )
        beta = self.client.post(self.url, json=beta_request)

        try:
            beta.raise_for_status()
        except:
            print(beta.content)
            raise
        return beta.content

    def compute_metric(self, geometry: dict) -> bytes:
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
            geometry,
        )

        sigma = self.client.post(self.url, json=sigma_request)
        try:
            sigma.raise_for_status()
        except:
            print(sigma.text)
            raise
        return sigma.content

    def base_request(self, data: list, evalscript: str, geometry: dict) -> dict:
        crs = "http://www.opengis.net/def/crs/EPSG/0/3857"
        return {
            "input": {
                "bounds": {
                    "geometry": geometry,
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

    def update_feature(self, feature: dict, monitor_data_json: list) -> dict:
        feature_id = feature["properties"][FEATURE_ID_COLUMN]
        geometry = feature["geometry"]
        monitor_request = self.base_request(
            monitor_data_json, prepare_evalscript(self.monitor_params, DATA_PATH.joinpath("predict.cjs")), geometry
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
            assert userdata_file
            # Read the content of userdata.json
            json_data = userdata_file.read().decode("utf-8")  # Decode from bytes to string

            # Parse the JSON string into a dictionary
            userdata_dict = json.loads(json_data)

            # Find the default.tif file
            output_tif = tar.extractfile("default.tif")  # Extract it in memory
            assert output_tif
            # Read and write the content of default.tif
            with MemoryFile(output_tif.read()) as memfile:
                write_monitor(memfile, self.s3, feature_id)
        return userdata_dict

    def monitor(self, end: datetime.date | None = None) -> dict:
        update_monitor_state(self.monitor_params.name, "UPDATING")
        self.monitor_params.state = "UPDATING"
        self.dump()
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
        results = {}
        for feature in self.geometries.iterfeatures():
            user_data = self.update_feature(feature, monitor_data_json)
            assert self.byoc_id
            vis_url = self.sh_configuration.create_vis_link(
                self.urls.vis_url,
                feature["properties"]["lat"],
                feature["properties"]["lng"],
                self.byoc_id,
                "DISTURBED-DATE",
                self.monitor_params.monitoring_start.strftime("%Y-%m-%d"),
            )
            user_data["link"] = vis_url
            feature_id = feature["properties"][FEATURE_ID_COLUMN]
            results[feature_id] = user_data

        # Save monitoring results to the database
        from .db import save_monitoring_results

        save_monitoring_results(self.monitor_params.name, results)

        self.monitor_params.last_monitored = end
        self.monitor_params.state = "INITIALIZED"
        update_monitor_state(self.monitor_params.name, "INITIALIZED")
        self.dump()
        return results

    def delete(self) -> None:
        """
        Deletes the S3 Folder for the monitor and the SH BYOC collection
        """
        update_monitor_state(self.monitor_params.name, "DELETING")
        self.monitor_params.state = "DELETING"
        self.dump()
        self.s3.delete()
        self.byoc.delete()
        self.sh_configuration.delete()
        self.monitor_params.state = "DELETED"
        update_monitor_state(self.monitor_params.name, "DELETED")
        self.dump()


class AsyncAPI(Backend):
    pass
