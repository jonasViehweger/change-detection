from datetime import date

import pytest
from dotenv import dotenv_values

import disturbancemonitor as dm


@pytest.fixture
def load_env(monkeypatch, request):
    """Load the specified .env file and apply its variables using monkeypatch."""
    env_file = request.param
    env_vars = dotenv_values(env_file)  # Read variables from the .env file
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)  # Set each variable in the test environment


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


@pytest.mark.parametrize(
    ("load_env", "endpoint"),
    [
        # (".env.tests.sh", "SENTINEL_HUB"),  # First test with AWS
        (".env.tests.cdse", "CDSE"),  # Second test with CDSE
    ],
    indirect=["load_env"],  # Use the load_env fixture indirectly
)
def test_process_api(load_env, endpoint, geojson_input):  # noqa: ARG001
    monitor_name = f"pytestProcessAPI{endpoint.replace('_', '')}"
    monitor = dm.start_monitor(
        name=monitor_name,
        monitoring_start=date(2023, 1, 1),
        geometry_path=geojson_input,
        id_column="MONITOR_FEATURE_ID",
        backend="ProcessAPI",
        overwrite=True,
        resolution=100,
        endpoint=endpoint,
    )
    del monitor
    monitor_reloaded = dm.load_monitor(monitor_name, backend="ProcessAPI")
    results = monitor_reloaded.monitor(end=date(2024, 1, 1))
    monitor_reloaded.delete()
    print(results)
