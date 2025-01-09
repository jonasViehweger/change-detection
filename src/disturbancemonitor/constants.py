from dataclasses import dataclass
from enum import Enum
from importlib.resources import files
from pathlib import Path
from typing import Literal

CONFIG_PATH = Path().home() / ".config" / "disturbancemonitor"
DATA_PATH = files("disturbancemonitor.data")
FEATURE_ID_COLUMN = "MONITOR_FEATURE_ID"


@dataclass
class EndpointConfig:
    base_url: str
    auth_url: str
    vis_url: str


class Endpoints(Enum):
    SENTINEL_HUB = EndpointConfig(
        base_url="https://services.sentinel-hub.com",
        auth_url="https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token",
        vis_url="https://apps.sentinel-hub.com/eo-browser/?",
    )
    CDSE = EndpointConfig(
        base_url="https://sh.dataspace.copernicus.eu",
        auth_url="https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
        vis_url="https://browser.dataspace.copernicus.eu/?",
    )


EndpointTypes = Literal["Sentinel Hub", "CDSE"]
