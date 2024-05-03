import json
from contextlib import suppress

import boto3
import s3fs
import xarray as xr


class Storage:
    def __init__(self, name, bucket_name):
        self.name = name
        self.bucket_name = bucket_name

    def create(self):
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
        beta_ds = xr.open_dataset(models, band_as_variable=True)
        order = ["y", "x"]
        reordered_indexes = {index_name: beta_ds.indexes[index_name] for index_name in order}
        beta_ds = beta_ds.reindex(reordered_indexes)
        beta_ds = beta_ds.rename({col: "c" + col[-1] for col in beta_ds})
        beta_ds["process"] = xr.zeros_like(beta_ds["c1"])
        s3_out = s3fs.S3FileSystem(anon=False, profile="default")
        store_out = s3fs.S3Map(root=f"s3://{self.bucket_name}/{self.name}", s3=s3_out, check=False)
        beta_ds.to_zarr(store_out, mode="a")

        metrics_ds = xr.open_dataset(metrics, band_as_variable=True)
        order = ["y", "x"]
        reordered_indexes = {index_name: metrics_ds.indexes[index_name] for index_name in order}
        metrics_ds = metrics_ds.rename({col: "metric" + col[-1] for col in metrics_ds})
        metrics_ds.to_zarr(store_out, mode="a")
