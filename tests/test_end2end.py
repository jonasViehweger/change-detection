from datetime import date

import pytest

import disturbancemonitor as dm


@pytest.fixture
def geojson_input(tmp_path):
    input_file = tmp_path / "valid.geojson"
    input_geojson_string = """
{
    "type": "FeatureCollection",
    "name": "pytestProcessAPI",
    "crs": { "type": "name", "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" } },
    "features": [
        { "type": "Feature", "properties": { "MONITOR_FEATURE_ID": 1 },
        "geometry": { "type": "Polygon", "coordinates": [ [
        [ -96.633894, 40.89311 ], [ -96.628745, 40.89311 ],
        [ -96.628745, 40.896549 ], [ -96.633894, 40.896549 ],
        [ -96.633894, 40.89311 ] ] ] } },
        { "type": "Feature", "properties": { "MONITOR_FEATURE_ID": 2 },
        "geometry": { "type": "Polygon", "coordinates": [ [
        [ -96.634092, 40.896499 ],
        [ -96.634092, 40.893122 ],
        [ -96.637665, 40.893133 ],
        [ -96.637653, 40.896464 ],
        [ -96.634092, 40.896499 ] ] ] } }
    ]
}

    """
    input_file.write_text(input_geojson_string)
    return input_file


def test_process_api(geojson_input):
    monitor = dm.start_monitor(
        name="pytestProcessAPI",
        monitoring_start=date(2023, 1, 1),
        geometry_path=geojson_input,
        id_column="id",
        backend="ProcessAPI",
        overwrite=True,
        resolution=1000,
    )
    del monitor
    monitor_reloaded = dm.load_monitor("pytestProcessAPI", backend="ProcessAPI")
    monitor_reloaded.monitor(end=date(2024, 1, 1))
