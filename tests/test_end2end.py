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


@pytest.mark.parametrize(
    ("load_env", "endpoint"),
    [
        # (".env.tests.sh", "SENTINEL_HUB"),  # First test with AWS
        (".env.tests.cdse", "CDSE"),  # Second test with CDSE
    ],
    indirect=["load_env"],  # Use the load_env fixture indirectly
)
def test_custom_config_path(load_env, endpoint, geojson_input, tmp_path):  # noqa: ARG001
    """Test full end-to-end workflow with custom config path."""
    # Create custom config file path
    custom_config_dir = tmp_path / "custom_configs"
    custom_config_dir.mkdir()
    custom_config_path = custom_config_dir / "test_monitor_config.gpkg"

    monitor_name = f"pytestCustomConfig{endpoint.replace('_', '')}"

    # Test 1: Initialize monitor with custom config path
    monitor = dm.start_monitor(
        name=monitor_name,
        monitoring_start=date(2023, 1, 1),
        geometry_path=geojson_input,
        id_column="MONITOR_FEATURE_ID",
        backend="ProcessAPI",
        overwrite=True,
        resolution=100,
        endpoint=endpoint,
        config_file_path=custom_config_path,
    )

    # Verify config file was created
    assert custom_config_path.exists(), "Custom config file should be created"

    # Test 2: Verify monitor exists in custom config
    config_handler = dm.get_geo_config(custom_config_path)
    assert config_handler.monitor_exists(monitor_name), "Monitor should exist in custom config"

    # Test 3: Verify monitor does NOT exist in default config (isolation test)
    default_config_handler = dm.get_geo_config()
    assert not default_config_handler.monitor_exists(monitor_name), "Monitor should NOT exist in default config"

    # Clean up monitor object
    del monitor

    # Test 4: Load monitor using custom config path
    monitor_reloaded = dm.load_monitor(monitor_name, backend="ProcessAPI", config_file_path=custom_config_path)

    # Verify loaded monitor has correct config
    assert monitor_reloaded.config.config_file_path == custom_config_path

    # Test 5: Monitor operation with custom config
    results = monitor_reloaded.monitor(end=date(2024, 1, 1))
    assert results is not None, "Monitor should return results"

    # Test 6: Verify results are stored in custom config
    stored_results = config_handler.load_monitoring_results(monitor_name)
    assert len(stored_results) > 0, "Results should be stored in custom config"

    # Test 7: Verify results are NOT in default config (isolation test)
    try:
        default_results = default_config_handler.load_monitoring_results(monitor_name)
        assert len(default_results) == 0, "Results should NOT be in default config"
    except KeyError:
        # Expected - monitor doesn't exist in default config
        pass

    # Test 8: Delete monitor using custom config
    monitor_reloaded.delete()

    # Test 9: Verify monitor is deleted from custom config
    assert not config_handler.monitor_exists(monitor_name), "Monitor should be deleted from custom config"

    # Test 10: Verify custom config file still exists but is cleaned up
    assert custom_config_path.exists(), "Custom config file should still exist after deletion"

    print(f"Custom config test completed successfully. Results: {results}")


def test_custom_config_basic(geojson_input, tmp_path):
    """Test basic custom config functionality without external dependencies."""
    # Create custom config file path
    custom_config_path = tmp_path / "basic_test_config.gpkg"

    # Test 1: Create config handler with custom path
    config = dm.get_geo_config(custom_config_path)
    assert config.config_file_path == custom_config_path

    # Test 2: Prepare geometry
    monitor_name = "basicTestMonitor"
    config.prepare_geometry(geojson_input, "MONITOR_FEATURE_ID", monitor_name)

    # Test 3: Create and save monitor parameters
    from datetime import date

    from disturbancemonitor.monitor_params import MonitorParameters

    params = MonitorParameters(
        name=monitor_name,
        monitoring_start=date(2023, 1, 1),
        last_monitored=date(2023, 1, 1),
        geometry_path=monitor_name,
        resolution=100.0,
    )

    config.save_monitor_params(params)

    # Test 4: Verify monitor exists
    assert config.monitor_exists(monitor_name), "Monitor should exist in custom config"

    # Test 5: Load monitor parameters
    loaded_params = config.load_monitor_params(monitor_name)
    assert loaded_params["name"] == monitor_name
    assert loaded_params["resolution"] == 100.0

    # Test 6: Load geometry
    geometry = config.load_geometry(monitor_name)
    assert len(geometry) > 0, "Geometry should be loaded"

    # Test 7: Verify isolation from default config
    default_config = dm.get_geo_config()
    assert not default_config.monitor_exists(monitor_name), "Monitor should NOT exist in default config"

    # Test 8: Verify config file exists
    assert custom_config_path.exists(), "Custom config file should exist"

    print("Basic custom config test completed successfully")


def test_free_cdse(geojson_input, tmp_path):
    """Test FreeCDSEProcessAPI initialization with different SH profiles."""

    # Create custom config to avoid affecting default
    custom_config_path = tmp_path / "test_freecdse_config.gpkg"
    config = dm.get_geo_config(custom_config_path)

    # Prepare test monitor parameters
    monitor_name = "testFreeCDSE"
    config.prepare_geometry(geojson_input, "MONITOR_FEATURE_ID", monitor_name)

    # Test 1: Initialize monitor with custom config path
    monitor = dm.start_monitor(
        name=monitor_name,
        monitoring_start=date(2023, 1, 1),
        geometry_path=geojson_input,
        id_column="MONITOR_FEATURE_ID",
        backend="FreeCDSEProcessAPI",
        overwrite=True,
        resolution=100,
        endpoint="CDSE",
        account_id="a0175978-820a-45e5-8ef2-8350e4a006f7",
        sh_profile="test-free-user",  # Free user credentials
        byoc_sh_profile="test-byoc-host",  # BYOC host credentials
        s3_profile="creo",
        config_file_path=custom_config_path,
    )

    # Clean up monitor object
    del monitor

    # Test 4: Load monitor using custom config path
    monitor_reloaded = dm.load_monitor(monitor_name, backend="FreeCDSEProcessAPI", config_file_path=custom_config_path)

    # Test 5: Monitor operation with custom config
    results = monitor_reloaded.monitor(end=date(2024, 1, 1))
    monitor_reloaded.delete()
    print(results)
