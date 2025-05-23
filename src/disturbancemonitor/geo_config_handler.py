import datetime
import logging
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd

from .constants import CONFIG_PATH, FEATURE_ID_COLUMN
from .monitor_params import MonitorParameters

# Set up logging
logger = logging.getLogger(__name__)

# Main GeoPackage file path
GEOPACKAGE_PATH = CONFIG_PATH / "monitor_config.gpkg"


class GeoConfigHandler:
    """
    Handles configuration and geometry data storage in a single GeoPackage file.
    GeoPackage stores geometries in a spatial table and configuration in non-spatial tables.
    """

    def __init__(self):
        # Ensure the directory exists
        CONFIG_PATH.mkdir(parents=True, exist_ok=True)
        logger.debug("Initializing GeoConfigHandler", extra={"config_path": str(CONFIG_PATH)})
        self._init_geopackage()

    def _init_geopackage(self) -> None:
        """Initialize the GeoPackage with necessary tables if they don't exist."""
        # Create an empty GeoPackage file if it doesn't exist
        if not GEOPACKAGE_PATH.exists():
            logger.info("Creating new GeoPackage file", extra={"geopackage_path": str(GEOPACKAGE_PATH)})
            # Create an empty GeoDataFrame and save it to establish the GeoPackage
            empty_gdf = gpd.GeoDataFrame([], geometry=[], crs="EPSG:3857")
            empty_gdf.to_file(GEOPACKAGE_PATH, driver="GPKG", layer="_init")

            # Create areas_of_interest layer with monitored_pixels column
            aoi_gdf = gpd.GeoDataFrame(
                [], columns=["monitor_name", FEATURE_ID_COLUMN, "lat", "lng"], geometry=[], crs="EPSG:3857"
            )
            aoi_gdf.to_file(GEOPACKAGE_PATH, driver="GPKG", layer="areas_of_interest")
        else:
            logger.debug("GeoPackage file already exists", extra={"geopackage_path": str(GEOPACKAGE_PATH)})

        # Connect to the GeoPackage's SQLite database for non-spatial tables
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create monitors table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS monitors (
            name TEXT PRIMARY KEY,
            monitoring_start TEXT NOT NULL,
            last_monitored TEXT NOT NULL,
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
        logger.debug("Created or verified monitors table")

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
        logger.debug("Created or verified backends table")

        # Create metadata table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        logger.debug("Created or verified metadata table")

        # Create monitoring_results table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS monitoring_results (
            monitor_name TEXT NOT NULL,
            feature_id TEXT NOT NULL,
            date TEXT NOT NULL,
            value INTEGER NOT NULL,
            PRIMARY KEY (monitor_name, feature_id, date),
            FOREIGN KEY (monitor_name) REFERENCES monitors(name) ON DELETE CASCADE
        )
        """)
        logger.debug("Created or verified monitoring_results table")

        # Insert schema version
        cursor.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", ("schema_version", "2"))
        logger.info("GeoPackage initialization completed with schema version 2")

        conn.commit()
        conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a connection to the SQLite database underlying the GeoPackage."""
        conn = sqlite3.connect(str(GEOPACKAGE_PATH))
        conn.row_factory = self._dict_factory
        conn.enable_load_extension(True)
        conn.load_extension("mod_spatialite")
        logger.debug("Established database connection", extra={"geopackage_path": str(GEOPACKAGE_PATH)})
        return conn

    @staticmethod
    def _dict_factory(cursor, row):
        """Convert SQLite row to dictionary."""
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def _adapt_date(self, date):
        """Convert date to ISO format for SQLite storage."""
        return date.isoformat() if date else None

    def _convert_date(self, date_str):
        """Convert ISO date string from SQLite to datetime.date."""
        if date_str and isinstance(date_str, bytes):
            date_str = date_str.decode("utf-8")
        return datetime.date.fromisoformat(str(date_str)) if date_str else None

    def save_geometry(self, monitor_name: str, gdf: gpd.GeoDataFrame) -> None:
        """
        Save geometries to the areas_of_interest table in the GeoPackage.

        Args:
            monitor_name: Name of the monitor to associate with the geometries
            gdf: GeoDataFrame containing the geometries
        """
        logger.info("Saving geometry for monitor", extra={"monitor_name": monitor_name, "geometry_count": len(gdf)})

        # Ensure the GeoDataFrame has the correct CRS
        if gdf.crs is None or gdf.crs.to_epsg() != 3857:
            logger.debug(
                "Reprojecting geometry to EPSG:3857", extra={"monitor_name": monitor_name, "original_crs": str(gdf.crs)}
            )
            gdf = gdf.to_crs(epsg=3857)

        # Add monitor_name column
        gdf["monitor_name"] = monitor_name

        # Ensure monitored_pixels column exists and is properly typed
        if "monitored_pixels" not in gdf.columns:
            gdf["monitored_pixels"] = None
        # Ensure the column is float64 to map to REAL in SQLite
        gdf["monitored_pixels"] = gdf["monitored_pixels"].astype("float64")

        # Explode any MultiPolygons into separate Polygons
        if any(gdf.geometry.type.isin(["MultiPolygon"])):
            logger.debug("Exploding MultiPolygons to Polygons", extra={"monitor_name": monitor_name})
            gdf = gdf.explode(index_parts=False)
            # Filter to keep only Polygon geometries
            gdf = gdf[gdf.geometry.type == "Polygon"]

        # Load existing areas_of_interest table
        try:
            existing_aoi = gpd.read_file(GEOPACKAGE_PATH, layer="areas_of_interest")

            # Delete any existing geometries for this monitor
            if not existing_aoi.empty and monitor_name in existing_aoi["monitor_name"].values:
                logger.debug("Removing existing geometries for monitor", extra={"monitor_name": monitor_name})
                existing_aoi = existing_aoi[existing_aoi["monitor_name"] != monitor_name]

            # Ensure existing_aoi has the same column types
            if not existing_aoi.empty and "monitored_pixels" in existing_aoi.columns:
                existing_aoi["monitored_pixels"] = existing_aoi["monitored_pixels"].astype("float64")

            # Concatenate with new geometries
            combined_aoi = pd.concat([existing_aoi, gdf], ignore_index=True)

            # Save back to GeoPackage
            combined_aoi.to_file(GEOPACKAGE_PATH, driver="GPKG", layer="areas_of_interest")
            logger.info(
                "Successfully saved geometry to areas_of_interest",
                extra={"monitor_name": monitor_name, "total_features": len(combined_aoi)},
            )
        except Exception as e:
            logger.error("Error updating areas_of_interest", extra={"monitor_name": monitor_name, "error": str(e)})
            # If there was an error, try to save just the new geometries
            gdf.to_file(GEOPACKAGE_PATH, driver="GPKG", layer="areas_of_interest")
            logger.warning("Saved only new geometries after error", extra={"monitor_name": monitor_name})

    def update_monitored_pixels(self, monitor_name: str, feature_id: str, monitored_pixels: int) -> None:
        """
        Update the monitored_pixels count for a specific feature in the areas_of_interest table.

        Args:
            monitor_name: Name of the monitor
            feature_id: Feature ID to update
            monitored_pixels: Number of monitored pixels
        """
        logger.debug(
            "Updating monitored pixels",
            extra={"monitor_name": monitor_name, "feature_id": feature_id, "monitored_pixels": monitored_pixels},
        )

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Ensure the column exists before trying to update
            cursor.execute("PRAGMA table_info(areas_of_interest)")
            columns = [row["name"] for row in cursor.fetchall()]
            if "monitored_pixels" not in columns:
                logger.debug("Adding monitored_pixels column to areas_of_interest table")
                cursor.execute("ALTER TABLE areas_of_interest ADD COLUMN monitored_pixels REAL")

            # Run update
            cursor.execute(
                f"""
                UPDATE areas_of_interest
                SET monitored_pixels = ?
                WHERE monitor_name = ? AND {FEATURE_ID_COLUMN} = ?
                """,
                (float(monitored_pixels), monitor_name, str(feature_id)),
            )

            if cursor.rowcount == 0:
                logger.warning(
                    "No matching row found for update", extra={"monitor_name": monitor_name, "feature_id": feature_id}
                )
            else:
                logger.info(
                    "Updated monitored_pixels successfully",
                    extra={
                        "monitor_name": monitor_name,
                        "feature_id": feature_id,
                        "monitored_pixels": monitored_pixels,
                    },
                )

            conn.commit()
        except Exception as e:
            logger.error(
                "SQL error updating monitored_pixels",
                extra={"monitor_name": monitor_name, "feature_id": feature_id, "error": str(e)},
            )
        finally:
            conn.close()

    def load_geometry(self, monitor_name: str | None = None) -> gpd.GeoDataFrame:
        """
        Load geometries for a monitor from the areas_of_interest table.

        Args:
            monitor_name: Name of the monitor to load geometries for

        Returns:
            GeoDataFrame containing the geometries
        """
        logger.debug("Loading geometry", extra={"monitor_name": monitor_name})

        try:
            # Load the areas_of_interest layer and filter for the monitor name
            aoi = gpd.read_file(GEOPACKAGE_PATH, layer="areas_of_interest")
            if aoi.empty:
                logger.warning("No geometries found in areas_of_interest table")
                raise KeyError(f"No geometries found for monitor '{monitor_name}'")
            if monitor_name is None:
                logger.debug("Returning all geometries", extra={"total_count": len(aoi)})
                return aoi

            filtered_aoi = aoi[aoi["monitor_name"] == monitor_name]

            if filtered_aoi.empty:
                logger.warning("No geometries found for monitor", extra={"monitor_name": monitor_name})
                raise KeyError(f"No geometries found for monitor '{monitor_name}'")

            logger.debug(
                "Successfully loaded geometry",
                extra={"monitor_name": monitor_name, "geometry_count": len(filtered_aoi)},
            )
            return filtered_aoi
        except Exception as e:
            logger.error("Error loading geometry for monitor", extra={"monitor_name": monitor_name, "error": str(e)})
            raise e

    def save_monitor_params(self, params: MonitorParameters) -> None:
        """
        Save monitor parameters to the GeoPackage.

        Args:
            params: Dictionary containing monitor parameters
        """
        logger.info("Saving monitor parameters", extra={"monitor_name": params.name})

        conn = self._get_connection()
        cursor = conn.cursor()
        # Convert to dict and ensure all values are compatible
        params_dict = asdict(params)

        # Remove geometry_path from params_dict as it's now stored in the areas_of_interest table
        params_dict.pop("geometry_path", None)
        name = params_dict.pop("name")

        # Handle dates
        for date_field in ["monitoring_start", "last_monitored"]:
            if isinstance(params_dict[date_field], datetime.date):
                params_dict[date_field] = params_dict[date_field].isoformat()

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

        logger.debug("Monitor parameters saved successfully", extra={"monitor_name": name, "fields": fields})
        conn.commit()
        conn.close()

    def save_backend_config(self, monitor_name: str, backend_type: str, config: dict[str, Any]) -> None:
        """
        Save backend configuration to the GeoPackage.

        Args:
            monitor_name: Name of the monitor
            backend_type: Type of the backend
            config: Dictionary containing backend configuration
        """
        logger.info("Saving backend configuration", extra={"monitor_name": monitor_name, "backend_type": backend_type})

        conn = self._get_connection()
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

        logger.debug(
            "Backend configuration saved successfully",
            extra={"monitor_name": monitor_name, "backend_type": backend_type, "config_fields": fields},
        )
        conn.commit()
        conn.close()

    def save_monitoring_results(self, monitor_name: str, results: dict[str, dict[str, Any]]) -> None:
        """
        Save monitoring results to the GeoPackage.

        Args:
            monitor_name: Name of the monitor
            results: Dictionary with feature IDs as keys and date-value mappings as values
        """
        logger.info("Saving monitoring results", extra={"monitor_name": monitor_name, "feature_count": len(results)})

        conn = self._get_connection()
        cursor = conn.cursor()

        # Prepare data for bulk insert
        data_to_insert = []
        sum_disturbed = 0
        for feature_id, feature_data in results.items():
            for date_str, value in feature_data.get("newDisturbed", {}).items():
                # Add the record to our insertion list
                data_to_insert.append(
                    (
                        monitor_name,
                        str(feature_id),
                        datetime.datetime.strptime(date_str, "%y%m%d").date().isoformat(),
                        value,
                    )
                )
                sum_disturbed += value

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
            logger.debug(
                "Monitoring results saved successfully",
                extra={"monitor_name": monitor_name, "records_inserted": len(data_to_insert)},
            )
            # Run update
            cursor.execute(
                f"""
                UPDATE areas_of_interest
                SET disturbed_pixels = disturbed_pixels + ?
                WHERE monitor_name = ? AND {FEATURE_ID_COLUMN} = ?
                """,
                (sum_disturbed, monitor_name, str(feature_id)),
            )
        else:
            logger.debug("No monitoring results to save", extra={"monitor_name": monitor_name})

        conn.commit()
        conn.close()

    def load_monitoring_results(self, monitor_name: str, feature_id: str | None = None) -> dict[str, dict[str, int]]:
        """
        Load monitoring results from the GeoPackage.

        Args:
            monitor_name: Name of the monitor
            feature_id: Optional feature ID to filter results

        Returns:
            Dictionary with feature IDs as keys and date-value mappings as values
        """
        logger.debug("Loading monitoring results", extra={"monitor_name": monitor_name, "feature_id": feature_id})

        conn = self._get_connection()
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
            date_str = row["date"]
            value = row["value"]

            if feature_id not in structured_results:
                structured_results[feature_id] = {}

            # Convert date string back to datetime.date
            date = datetime.date.fromisoformat(date_str) if date_str else None
            structured_results[feature_id][date] = value

        logger.debug(
            "Monitoring results loaded successfully",
            extra={
                "monitor_name": monitor_name,
                "feature_count": len(structured_results),
                "total_records": len(results),
            },
        )
        return structured_results

    def load_monitor_params(self, name: str) -> dict[str, Any]:
        """
        Load monitor parameters from the GeoPackage.

        Args:
            name: Name of the monitor

        Returns:
            Dictionary containing monitor parameters
        """
        logger.debug("Loading monitor parameters", extra={"monitor_name": name})

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM monitors WHERE name = ?", (name,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            logger.error("Monitor not found in database", extra={"monitor_name": name})
            raise KeyError(f"Monitor with name '{name}' not found in the database")

        # Convert date strings to datetime.date objects
        for date_field in ["monitoring_start", "last_monitored"]:
            if result.get(date_field):
                result[date_field] = datetime.date.fromisoformat(result[date_field])

        # Add the geometry_path to the params, pointing to the monitor name
        # This ensures backward compatibility
        result["geometry_path"] = name

        logger.debug("Monitor parameters loaded successfully", extra={"monitor_name": name})
        return result

    def load_backend_config(self, name: str, backend_type: str) -> dict[str, Any]:
        """
        Load backend configuration from the GeoPackage.

        Args:
            name: Name of the monitor
            backend_type: Type of the backend

        Returns:
            Dictionary containing backend configuration
        """
        logger.debug("Loading backend configuration", extra={"monitor_name": name, "backend_type": backend_type})

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM backends WHERE name = ? AND backend_type = ?", (name, backend_type))
        result = cursor.fetchone()
        conn.close()

        if not result:
            logger.error("Backend configuration not found", extra={"monitor_name": name, "backend_type": backend_type})
            raise KeyError(f"Backend configuration for monitor '{name}' with type {backend_type} not found")

        # Remove name and backend_type from the result
        result.pop("name", None)
        result.pop("backend_type", None)

        logger.debug(
            "Backend configuration loaded successfully", extra={"monitor_name": name, "backend_type": backend_type}
        )
        return result

    def load_all_monitors(self) -> list[str]:
        """
        Load all monitor names from the GeoPackage.

        Returns:
            List of monitor names
        """
        logger.debug("Loading all monitor names")

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM monitors")
        results = cursor.fetchall()
        conn.close()

        monitor_names = [row["name"] for row in results]
        logger.debug("All monitor names loaded", extra={"monitor_count": len(monitor_names)})
        return monitor_names

    def monitor_exists(self, name: str) -> bool:
        """
        Check if a monitor exists in the GeoPackage.

        Args:
            name: Name of the monitor

        Returns:
            True if the monitor exists, False otherwise
        """
        logger.debug("Checking if monitor exists", extra={"monitor_name": name})

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM monitors WHERE name = ?", (name,))
        result = cursor.fetchone()
        conn.close()

        exists = result is not None
        logger.debug("Monitor existence check completed", extra={"monitor_name": name, "exists": exists})
        return exists

    def backend_exists(self, name: str, backend_type: str) -> tuple[bool, bool, bool]:
        """
        Check if a monitor and its backend exists in the GeoPackage.

        Args:
            name: Name of the monitor
            backend_type: Type of the backend

        Returns:
            Tuple of (monitor_exists, backend_exists, is_initialized)
        """
        logger.debug(
            "Checking monitor and backend existence", extra={"monitor_name": name, "backend_type": backend_type}
        )

        conn = self._get_connection()
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

        logger.debug(
            "Monitor and backend existence check completed",
            extra={
                "monitor_name": name,
                "backend_type": backend_type,
                "monitor_exists": monitor_exists,
                "backend_exists": backend_exists,
                "is_initialized": is_initialized,
            },
        )
        return (monitor_exists, backend_exists, is_initialized)

    def delete_monitor(self, name: str) -> None:
        """
        Delete a monitor and its backends from the GeoPackage.

        Args:
            name: Name of the monitor
        """
        logger.info("Deleting monitor", extra={"monitor_name": name})

        conn = self._get_connection()
        cursor = conn.cursor()

        # Delete monitor (cascade will delete associated backends)
        cursor.execute("DELETE FROM monitors WHERE name = ?", (name,))
        deleted_rows = cursor.rowcount

        conn.commit()
        conn.close()

        # Delete the geometries associated with this monitor from areas_of_interest
        try:
            # Load existing areas_of_interest
            aoi = gpd.read_file(GEOPACKAGE_PATH, layer="areas_of_interest")

            # Filter out geometries for this monitor
            if not aoi.empty and name in aoi["monitor_name"].values:
                filtered_aoi = aoi[aoi["monitor_name"] != name]

                # Save back to GeoPackage
                filtered_aoi.to_file(GEOPACKAGE_PATH, driver="GPKG", layer="areas_of_interest")
                logger.info(
                    "Monitor and associated geometries deleted successfully",
                    extra={"monitor_name": name, "deleted_monitor_rows": deleted_rows},
                )
            else:
                logger.info(
                    "Monitor deleted (no associated geometries found)",
                    extra={"monitor_name": name, "deleted_monitor_rows": deleted_rows},
                )
        except Exception as e:
            logger.error("Error deleting geometries", extra={"monitor_name": name, "error": str(e)})

    def delete_monitoring_results(self, monitor_name: str, feature_id: str | None = None) -> None:
        """
        Delete monitoring results for a specific monitor and optional feature ID.

        Args:
            monitor_name: Name of the monitor
            feature_id: Optional feature ID to delete specific results
        """
        logger.info("Deleting monitoring results", extra={"monitor_name": monitor_name, "feature_id": feature_id})

        conn = self._get_connection()
        cursor = conn.cursor()

        if feature_id:
            cursor.execute(
                "DELETE FROM monitoring_results WHERE monitor_name = ? AND feature_id = ?",
                (monitor_name, str(feature_id)),
            )
        else:
            cursor.execute("DELETE FROM monitoring_results WHERE monitor_name = ?", (monitor_name,))

        deleted_rows = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(
            "Monitoring results deleted successfully",
            extra={"monitor_name": monitor_name, "feature_id": feature_id, "deleted_rows": deleted_rows},
        )

    def update_monitor_state(self, name: str, state: str) -> None:
        """
        Update the state of a monitor.

        Args:
            name: Name of the monitor
            state: New state
        """
        logger.info("Updating monitor state", extra={"monitor_name": name, "new_state": state})

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("UPDATE monitors SET state = ? WHERE name = ?", (state, name))
        updated_rows = cursor.rowcount

        conn.commit()
        conn.close()

        if updated_rows > 0:
            logger.debug("Monitor state updated successfully", extra={"monitor_name": name, "new_state": state})
        else:
            logger.warning("No monitor found to update state", extra={"monitor_name": name, "new_state": state})

    def prepare_geometry(self, input_path: str | Path, id_column: str, monitor_name: str) -> None:
        """
        Load a geometry file, reproject it to EPSG:3857, ensure the ID column is present,
        check for uniqueness, and save it to the areas_of_interest table.

        Args:
            input_path: Path to the input geometry file
            id_column: Name of the ID column in the input file
            monitor_name: Name of the monitor to associate with the geometries
        """
        logger.info(
            "Preparing geometry",
            extra={"input_path": str(input_path), "id_column": id_column, "monitor_name": monitor_name},
        )

        # Convert path-like objects to strings
        input_path_str = str(input_path) if isinstance(input_path, Path) else input_path

        # Load the input geometry with GeoPandas
        gdf = gpd.read_file(input_path_str).to_crs(epsg=3857).rename(columns={id_column: FEATURE_ID_COLUMN})
        logger.debug(
            "Loaded and reprojected geometry file", extra={"monitor_name": monitor_name, "feature_count": len(gdf)}
        )

        # Add WGS84 centroid
        centroids = gdf.to_crs(epsg=4326).centroid
        gdf["lat"] = centroids.y
        gdf["lng"] = centroids.x

        # Initialize monitored_pixels column as float64 to ensure REAL type in SQLite
        gdf["monitored_pixels"] = pd.Series(dtype="float64")
        gdf["disturbed_pixels"] = 0

        # Check for any geometries which aren't POLYGONS
        if not all(gdf.geometry.type == "Polygon"):
            logger.error(
                "Invalid geometry types found",
                extra={"monitor_name": monitor_name, "geometry_types": gdf.geometry.type.unique().tolist()},
            )
            raise ValueError("All geometries must be of type POLYGON")

        # Check for uniqueness in the id_column
        is_unique = gdf[FEATURE_ID_COLUMN].is_unique
        if not is_unique:
            logger.error(
                "Duplicate IDs found in geometry", extra={"monitor_name": monitor_name, "id_column": FEATURE_ID_COLUMN}
            )
            raise ValueError("Duplicate ID found")

        # Save to areas_of_interest in GeoPackage
        self.save_geometry(monitor_name, gdf)
        logger.info(
            "Geometry preparation completed successfully",
            extra={"monitor_name": monitor_name, "final_feature_count": len(gdf)},
        )

    def load_config(self) -> dict[str, Any]:
        """
        Load all configuration from the database in a format compatible with the old TOML format.
        This is for backward compatibility during migration.
        """
        # Get all monitors
        monitors = []
        for name in self.load_all_monitors():
            monitor_data = self.load_monitor_params(name)
            monitor_data["name"] = name
            monitors.append(monitor_data)

        # Build the config dictionary
        config = {}

        # Add monitor configurations
        for monitor in monitors:
            name = monitor.pop("name")
            config[name] = monitor

            # Load backends for this monitor
            conn = self._get_connection()
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


# Global instance for easy import
geo_config = GeoConfigHandler()
