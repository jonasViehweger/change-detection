import json
import os
from contextlib import suppress
from functools import wraps
from io import BytesIO
from time import sleep

import boto3
import boto3.session
import s3fs
import xarray as xr
from authlib.integrations.requests_client import OAuth2Session
from rasterio.io import MemoryFile
from requests.exceptions import HTTPError


class ResourceManager:
    def __init__(self, rollback=True):
        self.resources = []
        self.rollback = rollback

    def add_resource(self, resource):
        self.resources.append(resource)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            print(f"Exception occurred: {exc_val}. \nRolling back resources.")
            for resource in reversed(self.resources):
                if self.rollback:
                    resource.delete()
        return False  # Propagate the exception


def add_failure_message(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            response = func(*args, **kwargs)
            response.raise_for_status()
            return response
        except HTTPError as e:
            print(f"Request failed: {e.response.status_code} - {e.response.text}")
            raise

    return wrapper


class S3:
    def __init__(self, bucket_name, zarr_name, profile="default"):
        self.bucket_name = bucket_name
        self.zarr_name = zarr_name
        self.s3_out = s3fs.S3FileSystem(anon=False, profile=profile)
        self.session = boto3.session.Session(profile_name=profile)
        self.s3 = self.session.client("s3", region_name="eu-central-1")

    def create_bucket(self, policy):
        location = {"LocationConstraint": "eu-central-1"}
        with suppress(self.s3.exceptions.BucketAlreadyOwnedByYou):
            self.s3.create_bucket(Bucket=self.bucket_name, CreateBucketConfiguration=location)

        # Convert the policy from JSON dict to string
        bucket_policy = json.dumps(policy)

        # Set the new policy
        self.s3.put_bucket_policy(Bucket=self.bucket_name, Policy=bucket_policy)

    def write_zarr_store(self, ds):
        store_out = s3fs.S3Map(root=f"s3://{self.bucket_name}/{self.zarr_name}", s3=self.s3_out, check=False)
        ds.to_zarr(store_out, mode="a")

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

    def write_binary(self, filename: str, binary: BytesIO):
        with self.s3_out.open(filename, "wb") as f:
            f.write(binary.getvalue())

    def delete(self):
        """This is supposed to just delete the folder which was created, but not the bucket"""
        try:
            self.s3_out.delete(f"s3://{self.bucket_name}/{self.zarr_name}", recursive=True)
        except FileNotFoundError:
            pass
        self.s3.delete_bucket(Bucket=self.bucket_name)


class BYOC:
    def __init__(self, bucket_name, folder_name, sh_client, byoc_id=None) -> None:
        self.folder_name = folder_name
        self.bucket_name = bucket_name
        self.client = sh_client
        self.byoc_id = byoc_id
        self.url = "https://services.sentinel-hub.com/api/v1/byoc/collections"

    def create_byoc(self):
        new_collection = {"name": self.bucket_name, "s3Bucket": self.bucket_name}
        byoc = self.client.post(self.url, json=new_collection)
        byoc.raise_for_status()
        self.byoc_id = byoc.json()["data"]["id"]
        return self.byoc_id

    def ingest_tile(self, sensing_time):
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
            elif status == "FAILED":
                raise RuntimeError(
                    f'Ingestion of tile failed: {tile["data"]["additionalData"]["failedIngestionCause"]}'
                )
        print("... Ingested")
        return self.byoc_id

    def delete(self):
        """Delete the BYOC Collection"""
        delete = self.client.delete(f"{self.url}/{self.byoc_id}")
        delete.raise_for_status()


class ZarrSH:
    def __init__(self, zarr_name, bucket_name, sh_client, zarr_id=None) -> None:
        self.zarr_name = zarr_name
        self.bucket_name = bucket_name
        self.client = sh_client
        self.zarr_id = zarr_id
        self.zarr_api = "https://services.sentinel-hub.com/api/v1/zarr/collections"

    def ingest_dataset(self):
        # Make new Zarr storage on SH
        zarr_data = {
            "name": self.zarr_name,
            "s3Bucket": self.bucket_name,
            "path": f"{self.zarr_name}/",
            "crs": "http://www.opengis.net/def/crs/EPSG/0/4326",
        }
        zarr_byoc = self.client.post(self.zarr_api, json=zarr_data)
        zarr_byoc.raise_for_status()
        self.zarr_id = zarr_byoc.json()["data"]["id"]

        print("... Waiting for collection to finish ingestion")
        # wait for zarr collection to fully ingest
        while True:
            sleep(5)
            zarr_coll = self.client.get(f"{self.zarr_api}/{self.zarr_id}").json()
            if zarr_coll["data"]["status"] == "INGESTED":
                break
        print("... Ingested")
        return self.zarr_id

    def delete(self):
        """Delete the Zarr Collection"""
        delete = self.client.delete(f"{self.zarr_api}/{self.zarr_id}")
        delete.raise_for_status()


class SHClient:
    def __init__(self, profile="default-profile"):
        # TODO: make profile work.
        self.client = OAuth2Session(os.environ["SH_CLIENT_ID"], os.environ["SH_CLIENT_SECRET"])
        self.client.fetch_token("https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token")

    def get_token(self):
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
