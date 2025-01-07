import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

from disturbancemonitor import prepare_geometry


def create_test_file(geometry_list, id_column, file_path):
    """Helper function to create test GeoJSON files."""
    gdf = gpd.GeoDataFrame(
        {id_column: range(len(geometry_list))},
        geometry=geometry_list,
        crs="EPSG:4326",
    )
    gdf.to_file(file_path, driver="GeoJSON")


@pytest.fixture
def test_files(tmp_path):
    """Create test files for various cases."""
    valid_file = tmp_path / "valid.geojson"
    invalid_geom_file = tmp_path / "invalid_geom.geojson"
    duplicate_id_file = tmp_path / "duplicate_id.geojson"

    # Valid file with POLYGON geometries
    polygons = [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]) for _ in range(5)]
    create_test_file(polygons, "id", valid_file)

    # File with a non-POLYGON geometry (e.g., Point)
    geometries = [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])] * 4 + [Point(0, 0)]
    create_test_file(geometries, "id", invalid_geom_file)

    # File with duplicate IDs
    create_test_file(polygons, "id", duplicate_id_file)
    gdf = gpd.read_file(duplicate_id_file)
    gdf["id"] = [1, 2, 3, 3, 4]  # Introduce duplicate IDs
    gdf.to_file(duplicate_id_file, driver="GeoJSON")

    return {
        "valid": valid_file,
        "invalid_geom": invalid_geom_file,
        "duplicate_id": duplicate_id_file,
    }


def test_prepare_geometry_valid(test_files, tmp_path):
    """Test prepare_geometry with valid input."""
    output_file = tmp_path / "output.gpkg"
    prepare_geometry(test_files["valid"], "id", output_file)


def test_prepare_geometry_invalid_geometry(test_files, tmp_path):
    """Test prepare_geometry raises error for invalid geometries."""
    output_file = tmp_path / "output.gpkg"
    with pytest.raises(ValueError, match="All geometries must be of type POLYGON"):
        prepare_geometry(test_files["invalid_geom"], "id", output_file)


def test_prepare_geometry_duplicate_ids(test_files, tmp_path):
    """Test prepare_geometry raises error for duplicate IDs."""
    output_file = tmp_path / "output.gpkg"
    with pytest.raises(ValueError, match="Duplicate ID found"):
        prepare_geometry(test_files["duplicate_id"], "id", output_file)
