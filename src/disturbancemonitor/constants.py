from importlib.resources import files
from pathlib import Path

CONFIG_PATH = Path().home() / ".config" / "disturbancemonitor"
DATA_PATH = files("disturbancemonitor.data")
FEATURE_ID_COLUMN = "MONITOR_FEATURE_ID"
