import datetime
import json
import os
from contextlib import suppress
from io import BytesIO
from pathlib import Path
from time import sleep

import boto3
import boto3.session
import s3fs
import toml
from authlib.integrations.requests_client import OAuth2Session
from botocore.exceptions import ClientError
from requests.exceptions import HTTPError


class ResourceManager:
    def __init__(self, rollback: bool = True):
        self.resources = []
        self.rollback = rollback

    def add_resource(self, resource):
        self.resources.append(resource)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val):
        if exc_type:
            print(f"Exception occurred: {exc_val}. \nRolling back resources.")
            for resource in reversed(self.resources):
                if self.rollback:
                    resource.delete()
        return False  # Propagate the exception


class S3:
    def __init__(self, bucket_name: str, folder_name: str, profile: str = "default") -> None:
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

    def create_bucket(self, policy: dict) -> None:
        location = {"LocationConstraint": "eu-central-1"}
        with suppress(self.client.exceptions.BucketAlreadyOwnedByYou):
            self.client.create_bucket(Bucket=self.bucket_name, CreateBucketConfiguration=location)

        # Convert the policy from JSON dict to string
        bucket_policy = json.dumps(policy)

        # Set the new policy
        self.client.put_bucket_policy(Bucket=self.bucket_name, Policy=bucket_policy)

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

    def post(self, *args, **kwargs):
        self.get_token()
        return self.client.post(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.get_token()
        return self.client.delete(*args, **kwargs)

    def get(self, *args, **kwargs):
        self.get_token()
        return self.client.get(*args, **kwargs)


class BYOC:
    def __init__(self, bucket_name: str, folder_name: str, sh_client: SHClient, byoc_id: str | None = None) -> None:
        self.folder_name = folder_name
        self.bucket_name = bucket_name
        self.client = sh_client
        self.byoc_id = byoc_id
        self.url = "https://services.sentinel-hub.com/api/v1/byoc/collections"

    def create_byoc(self) -> str:
        new_collection = {"name": self.folder_name, "s3Bucket": self.bucket_name}
        byoc = self.client.post(self.url, json=new_collection)
        byoc.raise_for_status()
        self.byoc_id = byoc.json()["data"]["id"]
        return self.byoc_id

    def ingest_tile(self, sensing_time: datetime.date) -> None:
        tile_json = {"path": f"{self.folder_name}/(BAND).tif", "sensingTime": f"{sensing_time.isoformat()}T00:00:00Z"}
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
