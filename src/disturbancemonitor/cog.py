import os
from io import BytesIO

import numpy as np
import rasterio

from .resources import S3

_COG_PROFILE = {"driver": "COG", "compress": "DEFLATE", "blockxsize": 1024, "blockysize": 1024, "tiled": True}


def write_metric(in_path: str | os.PathLike, s3_resource: S3, feature_id: str | int) -> None:
    with rasterio.open(in_path) as src:
        profile = src.profile
        profile.update(**_COG_PROFILE)
        with BytesIO() as out:
            # Create a new file to write to
            with rasterio.open(out, "w", **profile) as dst:
                dst.write(src.read())
            s3_resource.write_binary(f"{s3_resource.root}/{feature_id},metric.tif", out)


def write_monitor(in_path: str | os.PathLike, s3_resource: S3, feature_id: str | int) -> None:
    with rasterio.open(in_path) as src:
        profile = src.profile
        profile.update(count=1, **_COG_PROFILE)
        with BytesIO() as out:
            with rasterio.open(out, "w", **profile) as dst:
                dst.write(src.read(1), 1)
            s3_resource.write_binary(f"{s3_resource.root}/{feature_id}/disturbedDate.tif", out)

        with BytesIO() as out:
            with rasterio.open(out, "w", **profile) as dst:
                dst.write(src.read(2), 1)
            s3_resource.write_binary(f"{s3_resource.root}/{feature_id}/process.tif", out)


def write_models(in_path: str | os.PathLike, s3_resource: S3, feature_id: str | int) -> None:
    with rasterio.open(in_path) as src:
        profile = src.profile
        profile.update(**_COG_PROFILE)
        with BytesIO() as out:
            # Create a new file to write to
            with rasterio.open(out, "w", **profile) as dst:
                dst.write(src.read())
            s3_resource.write_binary(f"{s3_resource.root}/{feature_id}/c.tif", out)

        # Init all other necessary files (files have only 1 band, init with 0)
        profile.update(count=1)
        zero_raster = np.zeros((profile["height"], profile["width"]), dtype=np.float32)
        with BytesIO() as out:
            with rasterio.open(out, "w", **profile) as dst:
                dst.write(zero_raster, 1)
            s3_resource.write_binary(f"{s3_resource.root}/{feature_id}/metric.tif", out)
            s3_resource.write_binary(f"{s3_resource.root}/{feature_id}/disturbedDate.tif", out)
            s3_resource.write_binary(f"{s3_resource.root}/{feature_id}/process.tif", out)
