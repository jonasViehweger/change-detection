import datetime
import logging
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

import toml

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

    # Insert schema version
    cursor.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", ("schema_version", "1"))

    conn.commit()
    conn.close()


def migrate_toml_to_sqlite() -> None:
    """Migrate existing TOML configurations to SQLite."""
    toml_path = CONFIG_PATH / "config.toml"

    if not toml_path.exists():
        logger.info("No TOML config found, skipping migration")
        return

    try:
        with open(toml_path) as configfile:
            config = toml.load(configfile)

        if not config:
            logger.info("Empty TOML config, skipping migration")
            return

        # Initialize the database
        init_db()
        conn = get_connection()
        cursor = conn.cursor()

        # Process each monitor configuration
        monitor_configs = {}
        backend_configs = {}

        for key, value in config.items():
            if "." in key:  # Backend configuration
                monitor_name, backend_type = key.split(".")
                backend_configs[(monitor_name, backend_type)] = value
            else:  # Monitor configuration
                monitor_configs[key] = value

        # Insert monitor configurations
        for name, monitor_config in monitor_configs.items():
            fields = list(monitor_config.keys())
            placeholders = ", ".join(["?"] * (len(fields) + 1))  # +1 for name

            cursor.execute(
                f"INSERT OR REPLACE INTO monitors (name, {', '.join(fields)}) VALUES ({placeholders})",
                [name] + [monitor_config[field] for field in fields],
            )

        # Insert backend configurations
        for (monitor_name, backend_type), backend_config in backend_configs.items():
            fields = list(backend_config.keys())
            placeholders = ", ".join(["?"] * (len(fields) + 2))  # +2 for name and backend_type

            cursor.execute(
                f"INSERT OR REPLACE INTO backends (name, backend_type, {', '.join(fields)}) VALUES ({placeholders})",
                [monitor_name, backend_type] + [backend_config[field] for field in fields],
            )

        conn.commit()
        conn.close()

        # Backup the old TOML file
        backup_path = toml_path.with_suffix(".toml.bak")
        toml_path.rename(backup_path)
        logger.info("TOML config migrated to SQLite and backed up")

    except Exception:
        logger.error("Failed to migrate TOML to SQLite")
        raise


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
