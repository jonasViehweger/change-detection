import datetime
import logging
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .constants import CONFIG_PATH
from .monitor_params import MonitorParameters

# Set up logging
logger = logging.getLogger(__name__)

# Database file path
DB_PATH = CONFIG_PATH / "config.db"


def dict_factory(cursor, row):
    """Convert SQLite row to dictionary."""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def adapt_date(date):
    """Convert date to ISO format for SQLite storage."""
    return date.isoformat() if date else None


def convert_date(date_str):
    """Convert ISO date string from SQLite to datetime.date."""
    if date_str and isinstance(date_str, bytes):
        date_str = date_str.decode("utf-8")
    return datetime.date.fromisoformat(str(date_str)) if date_str else None


sqlite3.register_adapter(datetime.date, adapt_date)
sqlite3.register_converter("DATE", convert_date)


def get_connection() -> sqlite3.Connection:
    """Get a connection to the SQLite database with proper settings."""
    # Ensure the directory exists
    CONFIG_PATH.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = dict_factory
    return conn


def init_db() -> None:
    """Initialize the database schema if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # Create monitors table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS monitors (
        name TEXT PRIMARY KEY,
        monitoring_start DATE NOT NULL,
        last_monitored DATE NOT NULL,
        geometry_path TEXT NOT NULL,
        resolution REAL NOT NULL,
        datasource TEXT NOT NULL,
        datasource_id TEXT,
        harmonics INTEGER NOT NULL,
        signal TEXT NOT NULL,
        metric TEXT NOT NULL,
        sensitivity REAL NOT NULL,
        boundary REAL NOT NULL,
        endpoint TEXT NOT NULL,
        state TEXT NOT NULL
    )
    """)

    # Create backends table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS backends (
        name TEXT NOT NULL,
        backend_type TEXT NOT NULL,
        bucket_name TEXT,
        folder_name TEXT,
        byoc_id TEXT,
        instance_id TEXT,
        monitor_id TEXT,
        s3_profile TEXT,
        sh_profile TEXT,
        rollback BOOLEAN,
        PRIMARY KEY (name, backend_type),
        FOREIGN KEY (name) REFERENCES monitors(name) ON DELETE CASCADE
    )
    """)

    # Create metadata table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # Create monitoring_results table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS monitoring_results (
        monitor_name TEXT NOT NULL,
        feature_id TEXT NOT NULL,
        date DATE NOT NULL,
        value INTEGER NOT NULL,
        PRIMARY KEY (monitor_name, feature_id, date),
        FOREIGN KEY (monitor_name) REFERENCES monitors(name) ON DELETE CASCADE
    )
    """)

    # Insert schema version
    cursor.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", ("schema_version", "1"))

    conn.commit()
    conn.close()


def save_monitor_params(params: MonitorParameters) -> None:
    """Save monitor parameters to the database."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    # Convert to dict and ensure all values are SQLite-compatible
    params_dict = asdict(params)
    name = params_dict.pop("name")

    # Convert PosixPath to string
    if isinstance(params_dict["geometry_path"], Path):
        params_dict["geometry_path"] = str(params_dict["geometry_path"])

    fields = list(params_dict.keys())
    placeholders = ", ".join(["?"] * len(fields))
    set_clause = ", ".join([f"{field} = ?" for field in fields])

    cursor.execute(
        f"""
        INSERT INTO monitors (name, {", ".join(fields)})
        VALUES (?, {placeholders})
        ON CONFLICT(name) DO UPDATE SET {set_clause}
        """,
        [name] + [params_dict[field] for field in fields] + [params_dict[field] for field in fields],
    )

    conn.commit()
    conn.close()


def save_backend_config(monitor_name: str, backend_type: str, config: dict[str, Any]) -> None:
    """Save backend configuration to the database."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    fields = list(config.keys())
    placeholders = ", ".join(["?"] * len(fields))
    set_clause = ", ".join([f"{field} = ?" for field in fields])

    cursor.execute(
        f"""
        INSERT INTO backends (name, backend_type, {", ".join(fields)})
        VALUES (?, ?, {placeholders})
        ON CONFLICT(name, backend_type) DO UPDATE SET {set_clause}
        """,
        [monitor_name, backend_type] + [config[field] for field in fields] + [config[field] for field in fields],
    )

    conn.commit()
    conn.close()


def save_monitoring_results(monitor_name: str, results: dict[int, dict[str, dict[str, int] | str]]) -> None:
    """
    Save monitoring results to the database.

    Args:
        monitor_name: Name of the monitor
        results: Dictionary with feature IDs as keys and date-value mappings as values
    """
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    # Prepare data for bulk insert
    data_to_insert = []

    for feature_id, feature_data in results.items():
        for date_str, value in feature_data["newDisturbed"].items():
            # Add the record to our insertion list
            data_to_insert.append(
                (monitor_name, str(feature_id), datetime.datetime.strptime(date_str, "%y%m%d").date(), value)
            )

    # Only proceed if there's data to insert
    if data_to_insert:
        # Use executemany for better performance
        cursor.executemany(
            """
            INSERT OR IGNORE INTO monitoring_results
            (monitor_name, feature_id, date, value)
            VALUES (?, ?, ?, ?)
            """,
            data_to_insert,
        )

    conn.commit()
    conn.close()


def load_monitoring_results(monitor_name: str, feature_id: str | None = None) -> dict[str, dict[str, int]]:
    """
    Load monitoring results from the database.

    Args:
        monitor_name: Name of the monitor
        feature_id: Optional feature ID to filter results

    Returns:
        Dictionary with feature IDs as keys and date-value mappings as values
    """
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    if feature_id:
        cursor.execute(
            """
            SELECT feature_id, date, value FROM monitoring_results
            WHERE monitor_name = ? AND feature_id = ?
            """,
            (monitor_name, str(feature_id)),
        )
    else:
        cursor.execute(
            """
            SELECT feature_id, date, value FROM monitoring_results
            WHERE monitor_name = ?
            """,
            (monitor_name,),
        )

    results = cursor.fetchall()
    conn.close()

    # Organize results into the expected structure
    structured_results = {}
    for row in results:
        feature_id = row["feature_id"]
        date = row["date"]
        value = row["value"]

        if feature_id not in structured_results:
            structured_results[feature_id] = {}

        structured_results[feature_id][date] = value

    return structured_results


def load_monitor_params(name: str) -> dict[str, Any]:
    """Load monitor parameters from the database."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM monitors WHERE name = ?", (name,))
    result = cursor.fetchone()
    conn.close()

    if not result:
        raise KeyError(f"Monitor with name '{name}' not found in the database")

    return result


def load_backend_config(name: str, backend_type: str) -> dict[str, Any]:
    """Load backend configuration from the database."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM backends WHERE name = ? AND backend_type = ?", (name, backend_type))
    result = cursor.fetchone()
    conn.close()

    if not result:
        raise KeyError(f"Backend configuration for monitor '{name}' with type '{backend_type}' not found")

    # Remove name and backend_type from the result
    result.pop("name", None)
    result.pop("backend_type", None)

    return result


def load_all_monitors() -> list[str]:
    """Load all monitor names from the database."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM monitors")
    results = cursor.fetchall()
    conn.close()

    return [row["name"] for row in results]


def monitor_exists(name: str) -> bool:
    """Check if a monitor exists in the database."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM monitors WHERE name = ?", (name,))
    result = cursor.fetchone()
    conn.close()

    return result is not None


def backend_exists(name: str, backend_type: str) -> tuple[bool, bool, bool]:
    """
    Check if a monitor and its backend exists in the database.

    Returns:
        Tuple of (monitor_exists, backend_exists, is_initialized)
    """
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    # Check if monitor exists
    cursor.execute("SELECT state FROM monitors WHERE name = ?", (name,))
    monitor_result = cursor.fetchone()
    monitor_exists = monitor_result is not None
    is_initialized = monitor_result["state"] == "INITIALIZED" if monitor_exists else False

    # Check if backend exists
    cursor.execute("SELECT 1 FROM backends WHERE name = ? AND backend_type = ?", (name, backend_type))
    backend_exists = cursor.fetchone() is not None

    conn.close()

    return (monitor_exists, backend_exists, is_initialized)


def delete_monitor(name: str) -> None:
    """Delete a monitor and its backends from the database."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    # Delete monitor (cascade will delete associated backends)
    cursor.execute("DELETE FROM monitors WHERE name = ?", (name,))

    conn.commit()
    conn.close()


def delete_monitoring_results(monitor_name: str, feature_id: str | None = None) -> None:
    """
    Delete monitoring results for a specific monitor and optional feature ID.

    Args:
        monitor_name: Name of the monitor
        feature_id: Optional feature ID to delete specific results
    """
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    if feature_id:
        cursor.execute(
            "DELETE FROM monitoring_results WHERE monitor_name = ? AND feature_id = ?", (monitor_name, str(feature_id))
        )
    else:
        cursor.execute("DELETE FROM monitoring_results WHERE monitor_name = ?", (monitor_name,))

    conn.commit()
    conn.close()


def update_monitor_state(name: str, state: str) -> None:
    """Update the state of a monitor."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE monitors SET state = ? WHERE name = ?", (state, name))

    conn.commit()
    conn.close()


def load_config() -> dict[str, Any]:
    """
    Load all configuration from the database in a format compatible with the old TOML format.
    This is for backward compatibility during migration.
    """
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    # Get all monitors
    cursor.execute("SELECT * FROM monitors")
    monitors = cursor.fetchall()

    # Get all backends
    cursor.execute("SELECT * FROM backends")
    backends = cursor.fetchall()

    conn.close()

    # Build the config dictionary
    config = {}

    # Add monitor configurations
    for monitor in monitors:
        name = monitor.pop("name")
        config[name] = monitor

    # Add backend configurations
    for backend in backends:
        name = backend.pop("name")
        backend_type = backend.pop("backend_type")
        config[f"{name}.{backend_type}"] = backend

    return config
