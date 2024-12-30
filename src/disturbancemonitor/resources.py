import datetime
import json
import os
from contextlib import suppress
from io import BytesIO
from pathlib import Path
from time import sleep
from types import TracebackType
from typing import Literal

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
        self.client = self.session.client("s3", region_name="eu-central-1")

    def update_policy(self, new_statements: list):
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

    def create_bucket(self) -> None:
        location = {"LocationConstraint": "eu-central-1"}
        with suppress(self.client.exceptions.BucketAlreadyOwnedByYou):
            self.client.create_bucket(Bucket=self.bucket_name, CreateBucketConfiguration=location)

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
    def __init__(self, profile: str = "default-profile") -> None:
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
        self.client.fetch_token("https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token")

    def get_token(self) -> None:
        if self.client.token.is_expired():
            self.client.fetch_token("https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token")

    def post(self, *args, **kwargs) -> Response:
        self.get_token()
        return self.client.post(*args, **kwargs)

    def delete(self, *args, **kwargs) -> Response:
        self.get_token()
        return self.client.delete(*args, **kwargs)

    def get(self, *args, **kwargs) -> Response:
        self.get_token()
        return self.client.get(*args, **kwargs)


class BYOC(Resource):
    def __init__(
        self,
        bucket_name: str,
        folder_name: str,
        sh_client: SHClient,
        byoc_id: str | None = None,
    ) -> None:
        self.folder_name = folder_name
        self.bucket_name = bucket_name
        self.client = sh_client
        self.byoc_id = byoc_id
        self.url = "https://services.sentinel-hub.com/api/v1/byoc/collections"

    def create_byoc(self) -> str | None:
        new_collection = {"name": self.folder_name, "s3Bucket": self.bucket_name}
        byoc = self.client.post(self.url, json=new_collection)
        byoc.raise_for_status()
        self.byoc_id = byoc.json()["data"]["id"]
        return self.byoc_id

    def ingest_tile(self, sensing_time: datetime.date) -> None:
        tile_json = {
            "path": f"{self.folder_name}/(BAND).tif",
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
                    f'Ingestion of tile failed: {tile["data"]["additionalData"]["failedIngestionCause"]}'
                )
        print("... Ingested")

    def delete(self) -> None:
        """Delete the BYOC Collection"""
        delete = self.client.delete(f"{self.url}/{self.byoc_id}")
        delete.raise_for_status()


class SHConfiguration(Resource):
    def __init__(
        self,
        sh_client: SHClient,
        monitor_name: str,
        byoc_id: str,
    ):
        self.client = sh_client
        self.byoc_id = byoc_id
        self.monitor_name = monitor_name
        self.url = "https://services.sentinel-hub.com/configuration/v1/wms/instances"

    def create_instance(self) -> None:
        instance_data = {
            "name": f"Disturbance Monitor - {self.monitor_name}",
            "description": "Output of the disturbance monitoring",
        }
        instance = self.client.post(self.url, json=instance_data)
        try:
            instance.raise_for_status()
        except HTTPError as e:
            print(f"Request failed: {e.response.status_code} - {e.response.text}")
            raise
        self.instance_id = instance.json()["id"]

    def create_layer(self, title: str, evalscript: str) -> None:
        layer = {
            "title": title,
            "id": title.upper(),
            "description": "",
            "datasetSource": {
                "@id": "https://services.sentinel-hub.com/configuration/v1/datasets/CUSTOM/sources/10",
                "id": 10,
                "description": "Bring Your Own COG",
                "settings": {"indexServiceUrl": "https://services.sentinel-hub.com/byoc"},
                "dataset": {"@id": "https://services.sentinel-hub.com/configuration/v1/datasets/CUSTOM"},
            },
            "dataset": {"@id": "https://services.sentinel-hub.com/configuration/v1/datasets/CUSTOM"},
            "styles": [{"name": "default", "description": "Default layer style", "evalScript": evalscript}],
            "instanceId": self.instance_id,
            "defaultStyleName": "default",
            "datasourceDefaults": {"type": "CUSTOM", "mosaickingOrder": "mostRecent", "collectionId": self.byoc_id},
        }
        layer_response = self.client.post(f"{self.url}/{self.instance_id}/layers", json=layer)
        try:
            layer_response.raise_for_status()
        except HTTPError as e:
            print(layer)
            print(f"Request failed: {e.response.status_code} - {e.response.text}")
            raise

    def delete(self) -> None:
        """Delete the Configuration"""
        delete = self.client.delete(f"{self.url}/{self.instance_id}")
        delete.raise_for_status()
