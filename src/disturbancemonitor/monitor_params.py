import datetime
from dataclasses import dataclass
from os import PathLike
from typing import Literal

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

    @property
    def fit_start(self) -> datetime.date:
        return self.monitoring_start - datetime.timedelta(days=365)
