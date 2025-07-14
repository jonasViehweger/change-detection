import datetime
import json
import os
from contextlib import suppress
from io import BytesIO
from pathlib import Path
from time import sleep
from types import TracebackType
from typing import Any, Literal

import boto3
import boto3.session
import s3fs
import toml
from authlib.integrations.requests_client import OAuth2Session
from botocore.exceptions import ClientError
from requests import Response
from requests.exceptions import HTTPError


class Resource:
    def delete(self) -> None:
        raise NotImplementedError("Method delete() must be implemented in subclass.")


class ResourceManager:
    def __init__(self, rollback: bool = True):
        self.resources: list[Resource] = []
        self.rollback = rollback

    def add_resource(self, resource: Resource) -> None:
        self.resources.append(resource)

    def __enter__(self) -> "ResourceManager":
        return self

    def __exit__(
        self, exc_type: BaseException | None, exc_val: BaseException | None, tb: TracebackType | None
    ) -> Literal[False]:
        if exc_type:
            print(f"Exception occurred: {exc_val}. \nRolling back resources.")
            for resource in reversed(self.resources):
                if self.rollback:
                    resource.delete()
        return False  # Propagate the exception


class S3(Resource):
    def __init__(self, bucket_name: str, folder_name: str, profile: str | None = None) -> None:
        """
        Initializes an S3 object.

        Args:
            bucket_name (str): The name of the S3 bucket.
            folder_name (str): The name of the folder within the S3 bucket.
            profile (str, optional): The name of the AWS profile to use. Defaults to "default".
        """
        self.bucket_name = bucket_name
        self.folder_name = folder_name
        self.root = f"s3://{self.bucket_name}/{self.folder_name}"
        self.s3fs = s3fs.S3FileSystem(anon=False, profile=profile)
        self.session = boto3.session.Session(profile_name=profile)
        self.client = self.session.client("s3")

    def update_policy(self, new_statements: list) -> None:
        # Get bucket policy
        try:
            old_policy = json.loads(self.client.get_bucket_policy(Bucket=self.bucket_name)["Policy"])
        except self.client.exceptions.from_code("NoSuchBucketPolicy"):
            old_policy = {"Version": "2012-10-17", "Statement": []}
        # Check if there's already a statement with that name
        available_statements = {statement["Sid"] for statement in old_policy["Statement"]}
        for new_statement in new_statements:
            if new_statement["Sid"] not in available_statements:
                old_policy["Statement"].append(new_statement)
        # Convert the policy from JSON dict to string
        new_policy = json.dumps(old_policy)
        # Set the new policy
        self.client.put_bucket_policy(Bucket=self.bucket_name, Policy=new_policy)

    def create_bucket(self, bucket_location: dict | None) -> None:
        with suppress(self.client.exceptions.BucketAlreadyOwnedByYou):
            if bucket_location is None:
                self.client.create_bucket(Bucket=self.bucket_name)
            else:
                self.client.create_bucket(Bucket=self.bucket_name, CreateBucketConfiguration=bucket_location)

    def write_binary(self, filename: str, binary: BytesIO) -> None:
        with self.s3fs.open(filename, "wb") as f:
            f.write(binary.getvalue())

    def delete(self) -> None:
        """
        Tries to delete the folder and the bucket, if the bucket is empty.
        """
        with suppress(FileNotFoundError):
            self.s3fs.delete(f"s3://{self.bucket_name}/{self.folder_name}", recursive=True)
        # try to delete the bucket if its empty
        with suppress(ClientError):
            self.client.delete_bucket(Bucket=self.bucket_name)


class SHClient:
    def __init__(self, auth_url: str, profile: str = "default-profile") -> None:
        """
        Initializes a new instance of SHClient. This class takes care of handling the OAuth2 authentication with
        Sentinel Hub services. First priority is given to the environment variables SH_CLIENT_ID and SH_CLIENT_SECRET.

        If those are not set, the client ID and secret are read from the Sentinel Hub configuration file located at
        ~/.config/sentinelhub/config.toml.

        Args:
            profile (str): The profile name to use for retrieving the client ID and secret.
        """
        if os.environ.get("SH_CLIENT_ID") is not None and os.environ.get("SH_CLIENT_SECRET") is not None:
            self.client = OAuth2Session(os.environ["SH_CLIENT_ID"], os.environ["SH_CLIENT_SECRET"])
        else:
            with open(Path().home() / ".config" / "sentinelhub" / "config.toml") as configfile:
                sh_config = toml.load(configfile)[profile]
            self.client = OAuth2Session(sh_config["sh_client_id"], sh_config["sh_client_secret"])
        self.auth_url = auth_url
        self.client.fetch_token(self.auth_url)

    def get_token(self) -> None:
        if self.client.token.is_expired():
            self.client.fetch_token(self.auth_url)

    def post(self, *args: Any, **kwargs: Any) -> Response:
        self.get_token()
        return self.client.post(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> Response:
        self.get_token()
        return self.client.delete(*args, **kwargs)

    def get(self, *args: Any, **kwargs: Any) -> Response:
        self.get_token()
        return self.client.get(*args, **kwargs)


class BYOC(Resource):
    def __init__(
        self,
        base_url: str,
        bucket_name: str,
        folder_name: str,
        sh_client: SHClient,
        byoc_id: str | None = None,
    ) -> None:
        self.folder_name = folder_name
        self.bucket_name = bucket_name
        self.client = sh_client
        self.base_url = base_url
        self.byoc_id = byoc_id
        self.url = base_url + "/api/v1/byoc/collections"

    def create_byoc(self) -> str:
        new_collection = {"name": self.folder_name, "s3Bucket": self.bucket_name}
        byoc = self.client.post(self.url, json=new_collection)
        byoc.raise_for_status()
        self.byoc_id = byoc.json()["data"]["id"]
        assert isinstance(self.byoc_id, str)
        return self.byoc_id

    def ingest_tile(self, sensing_time: datetime.date, feature_id: str | int) -> None:
        tile_json = {
            "path": f"{self.folder_name}/{feature_id}/(BAND).tif",
            "sensingTime": f"{sensing_time.isoformat()}T00:00:00Z",
        }
        try:
            tile_request = self.client.post(f"{self.url}/{self.byoc_id}/tiles", json=tile_json)
            tile_request.raise_for_status()
        except HTTPError as e:
            print(f"Request failed: {e.response.status_code} - {e.response.text}")
            raise
        tile_id = tile_request.json()["data"]["id"]

        print("... Waiting for collection to finish ingestion")
        # wait for zarr collection to fully ingest
        while True:
            sleep(5)
            tile = self.client.get(f"{self.url}/{self.byoc_id}/tiles/{tile_id}").json()
            status = tile["data"]["status"]
            if status == "INGESTED":
                break
            if status == "FAILED":
                raise RuntimeError(
                    f"Ingestion of tile failed: {tile['data']['additionalData']['failedIngestionCause']}"
                )
        print("... Ingested")

    def share_byoc(self, account_id: str):
        """Shares a collection with an account"""
        response = self.client.post(f"{self.base_url}/api/v1/acl/collection/{self.byoc_id}/da/{account_id}/USE?notes=")
        response.raise_for_status()

    def delete(self) -> None:
        """Delete the BYOC Collection"""
        r = self.client.delete(f"{self.url}/{self.byoc_id}")
        with suppress(HTTPError):
            r.raise_for_status()


class SHConfiguration(Resource):
    def __init__(
        self,
        base_url: str,
        sh_client: SHClient,
        monitor_name: str,
        instance_id: str | None = None,
    ):
        self.client = sh_client
        self.monitor_name = monitor_name
        self.base_url = base_url
        self.url = base_url + "/configuration/v1"
        self.instance_id = instance_id

    def create_instance(self) -> str:
        instance_data = {
            "name": f"Disturbance Monitor - {self.monitor_name}",
            "description": "Output of the disturbance monitoring",
            "additionalData": {"showWarnings": False, "showLogo": False, "imageQuality": 80, "disabled": False},
        }
        instance = self.client.post(self.url + "/wms/instances", json=instance_data)
        try:
            instance.raise_for_status()
        except HTTPError as e:
            print(f"Request failed: {e.response.status_code} - {e.response.text}")
            raise
        self.instance_id = instance.json()["id"]
        assert isinstance(self.instance_id, str)
        return self.instance_id

    def create_layer(self, title: str, evalscript: str, byoc_id: str) -> None:
        layer = {
            "title": title,
            "id": title.upper(),
            "description": "",
            "datasetSource": {
                "@id": f"{self.url}/datasets/CUSTOM/sources/10",
                "id": 10,
                "description": "Bring Your Own COG",
                "settings": {"indexServiceUrl": f"{self.base_url}/byoc"},
                "dataset": {"@id": f"{self.url}/datasets/CUSTOM"},
            },
            "dataset": {"@id": f"{self.url}/datasets/CUSTOM"},
            "styles": [{"name": "default", "description": "Default layer style", "evalScript": evalscript}],
            "instanceId": self.instance_id,
            "defaultStyleName": "default",
            "datasourceDefaults": {"type": "CUSTOM", "mosaickingOrder": "mostRecent", "collectionId": byoc_id},
        }
        layer_response = self.client.post(f"{self.url}/wms/instances/{self.instance_id}/layers", json=layer)
        try:
            layer_response.raise_for_status()
        except HTTPError as e:
            print(layer)
            print(f"Request failed: {e.response.status_code} - {e.response.text}")
            raise

    def create_vis_link(self, root_url: str, lat: float, lng: float, byoc_id: str, layer_id: str, date: str) -> str:
        query_params = {
            "zoom": 16,
            "lat": lat,
            "lng": lng,
            "themeId": self.instance_id,
            "datasetId": byoc_id,
            "fromTime": f"{date}T00:00:00.000Z",
            "toTime": f"{date}T00:00:00.000Z",
            "layerId": layer_id,
        }
        return root_url + "&".join([f"{k}={v}" for k, v in query_params.items()])

    def delete(self) -> None:
        """Delete the Configuration"""
        r = self.client.delete(f"{self.url}/wms/instances/{self.instance_id}")
        with suppress(HTTPError):
            r.raise_for_status()
