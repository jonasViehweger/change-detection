import os
from dataclasses import dataclass
from enum import Enum
from importlib.resources import files
from pathlib import Path
from typing import Literal, get_args

DEFAULT_CONFIG_PATH = Path().home() / ".config" / "disturbancemonitor"
DEFAULT_CONFIG_FILE = "monitor_config.gpkg"


def get_default_config_file_path() -> Path:
    """Get the default configuration file path, with environment variable override support."""
    config_dir = os.getenv("DISTURBANCEMONITOR_CONFIG_DIR")
    config_file = os.getenv("DISTURBANCEMONITOR_CONFIG_FILE", DEFAULT_CONFIG_FILE)

    if config_dir:
        return Path(config_dir) / config_file
    return DEFAULT_CONFIG_PATH / config_file


DATA_PATH = files("disturbancemonitor.data")
FEATURE_ID_COLUMN = "MONITOR_FEATURE_ID"


@dataclass
class EndpointConfig:
    base_url: str
    auth_url: str
    vis_url: str
    byoc_principal: str
    bucket_location: dict | None


class Endpoints(Enum):
    SENTINEL_HUB = EndpointConfig(
        base_url="https://services.sentinel-hub.com",
        auth_url="https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token",
        vis_url="https://apps.sentinel-hub.com/eo-browser/?",
        byoc_principal="arn:aws:iam::614251495211:root",
        bucket_location={"LocationConstraint": "eu-central-1"},
    )
    CDSE = EndpointConfig(
        base_url="https://sh.dataspace.copernicus.eu",
        auth_url="https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
        vis_url="https://browser.dataspace.copernicus.eu/?",
        byoc_principal="arn:aws:iam::ddf4c98b5e6647f0a246f0624c8341d9:root",
        bucket_location=None,
    )


EndpointTypes = Literal["SENTINEL_HUB", "CDSE"]

# Assert that endpoints enum and available str types don't go out of sync
assert set(get_args(EndpointTypes)) == {member.name for member in Endpoints}
