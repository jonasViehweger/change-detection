from datetime import date

import pytest
from dotenv import find_dotenv, load_dotenv

import disturbancemonitor as dm


@pytest.fixture(scope="session", autouse=True)
def load_env():
    env_file = find_dotenv(".env.tests")
    load_dotenv(env_file)


@pytest.fixture
def geojson_input():
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [-96.633894, 40.89311],
                [-96.628745, 40.89311],
                [-96.628745, 40.896549],
                [-96.633894, 40.896549],
                [-96.633894, 40.89311],
            ]
        ],
    }


def test_process_api(geojson_input):
    monitor = dm.start_monitor(
        name="pytestProcessAPI",
        monitoring_start=date(2023, 1, 1),
        geometry=geojson_input,
        backend="ProcessAPI",
        overwrite=True,
    )
    del monitor
    monitor_reloaded = dm.load_monitor("pytestProcessAPI", backend="ProcessAPI")
    monitor_reloaded.monitor(end=date(2024, 1, 1))
