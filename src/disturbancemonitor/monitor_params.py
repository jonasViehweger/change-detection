import datetime
from dataclasses import asdict, dataclass
from os import PathLike
from typing import Any, Literal

from .constants import EndpointTypes

datasource_ids = {"S2L2A": "sentinel-2-l2a"}


@dataclass
class MonitorParameters:
    name: str
    monitoring_start: datetime.date
    last_monitored: datetime.date
    geometry_path: str | PathLike
    resolution: float
    datasource: Literal["S2L2A", "ARPS"] = "S2L2A"
    datasource_id: str | None = None
    harmonics: int = 2
    signal: Literal["NDVI"] = "NDVI"
    metric: Literal["RMSE"] = "RMSE"
    sensitivity: float = 5
    boundary: float = 5
    endpoint: EndpointTypes = "SENTINEL_HUB"
    state: str = "NOT_INITIALIZED"

    def __post_init__(self) -> None:
        if self.datasource_id is None:
            self.datasource_id = datasource_ids[self.datasource]

        # Convert PathLike objects to strings
        if isinstance(self.geometry_path, PathLike):
            self.geometry_path = str(self.geometry_path)

    @property
    def fit_start(self) -> datetime.date:
        return self.monitoring_start - datetime.timedelta(days=365)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MonitorParameters":
        """
        Create a MonitorParameters instance from a dictionary.
        This is useful when loading from the database.
        """
        # Filter out any keys that aren't valid parameters
        valid_keys = {field.name for field in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}

        return cls(**filtered_data)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the parameters to a dictionary for database storage.
        """
        data = asdict(self)
        # Ensure PathLike objects are converted to strings
        if isinstance(data["geometry_path"], PathLike):
            data["geometry_path"] = str(data["geometry_path"])
        return data
