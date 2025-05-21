import logging
from dataclasses import asdict
from os import PathLike
from pathlib import Path
from typing import Any

from .geo_config_handler import geo_config
from .monitor_params import MonitorParameters

# Set up logging
logger = logging.getLogger(__name__)


def init_db() -> None:
    """Initialize the database schema if it doesn't exist."""
    # This function now just ensures the GeoConfigHandler is initialized
    # The actual initialization happens in the GeoConfigHandler constructor


def save_monitor_params(params: MonitorParameters) -> None:
    """Save monitor parameters to the database."""
    # Convert to dict and ensure all values are compatible
    params_dict = asdict(params)

    # Remove geometry_path from params_dict as it's now stored in the GeoPackage layer
    params_dict.pop("geometry_path", None)

    # Save the monitor parameters
    geo_config.save_monitor_params(params_dict)


def save_backend_config(monitor_name: str, backend_type: str, config: dict[str, Any]) -> None:
    """Save backend configuration to the database."""
    geo_config.save_backend_config(monitor_name, backend_type, config)


def save_monitoring_results(monitor_name: str, results: dict[str, dict[str, Any]]) -> None:
    """
    Save monitoring results to the database.

    Args:
        monitor_name: Name of the monitor
        results: Dictionary with feature IDs as keys and date-value mappings as values
    """
    geo_config.save_monitoring_results(monitor_name, results)


def load_monitoring_results(monitor_name: str, feature_id: str | None = None) -> dict[str, dict[str, int]]:
    """
    Load monitoring results from the database.

    Args:
        monitor_name: Name of the monitor
        feature_id: Optional feature ID to filter results

    Returns:
        Dictionary with feature IDs as keys and date-value mappings as values
    """
    return geo_config.load_monitoring_results(monitor_name, feature_id)


def load_monitor_params(name: str) -> dict[str, Any]:
    """Load monitor parameters from the database."""
    params = geo_config.load_monitor_params(name)

    # Add the geometry path to the params
    # This path is now virtual, pointing to the layer in the GeoPackage
    params["geometry_path"] = name

    return params


def load_backend_config(name: str, backend_type: str) -> dict[str, Any]:
    """Load backend configuration from the database."""
    return geo_config.load_backend_config(name, backend_type)


def load_all_monitors() -> list[str]:
    """Load all monitor names from the database."""
    return geo_config.load_all_monitors()


def monitor_exists(name: str) -> bool:
    """Check if a monitor exists in the database."""
    return geo_config.monitor_exists(name)


def backend_exists(name: str, backend_type: str) -> tuple[bool, bool, bool]:
    """
    Check if a monitor and its backend exists in the database.

    Returns:
        Tuple of (monitor_exists, backend_exists, is_initialized)
    """
    return geo_config.backend_exists(name, backend_type)


def delete_monitor(name: str) -> None:
    """Delete a monitor and its backends from the database."""
    geo_config.delete_monitor(name)


def delete_monitoring_results(monitor_name: str, feature_id: str | None = None) -> None:
    """
    Delete monitoring results for a specific monitor and optional feature ID.

    Args:
        monitor_name: Name of the monitor
        feature_id: Optional feature ID to delete specific results
    """
    geo_config.delete_monitoring_results(monitor_name, feature_id)


def update_monitor_state(name: str, state: str) -> None:
    """Update the state of a monitor."""
    geo_config.update_monitor_state(name, state)


def prepare_geometry(geometry_path: str | PathLike, id_column: str, output_path: str | PathLike) -> None:
    """
    Load a geometry file, reproject it to EPSG:3857, set the column name to the id_column,
    check if all values in the id column are unique, and store it in the GeoPackage.

    Parameters:
    - geometry_path (str | PathLike): Path to the input geometry file.
    - id_column (str): The name of the column to be used as the ID column.
    - output_path (str | PathLike): Not used directly; derived monitor name from this path.
    """
    # Extract the monitor name from the output path
    output_path_str = str(output_path) if isinstance(output_path, PathLike) else output_path
    monitor_name = Path(output_path_str).stem  # Get filename without extension

    # Use GeoConfigHandler to prepare and store the geometry
    geo_config.prepare_geometry(geometry_path, id_column, monitor_name)


def load_config() -> dict[str, Any]:
    """
    Load all configuration from the database in a format compatible with the old TOML format.
    This is for backward compatibility during migration.
    """
    # Get all monitors
    monitors = []
    for name in geo_config.load_all_monitors():
        monitor_data = geo_config.load_monitor_params(name)
        monitor_data["name"] = name
        monitors.append(monitor_data)

    # Build the config dictionary
    config = {}

    # Add monitor configurations
    for monitor in monitors:
        name = monitor.pop("name")
        config[name] = monitor

        # Load backends for this monitor
        conn = geo_config._get_connection()  # noqa: SLF001
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM backends WHERE name = ?", (name,))
        backends = cursor.fetchall()
        conn.close()

        # Add backend configurations
        for backend in backends:
            backend_type = backend.pop("backend_type")
            backend.pop("name")
            config[f"{name}.{backend_type}"] = backend

    return config
