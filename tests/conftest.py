import json
import os
from pathlib import Path

import pytest

from iris_oek.config import Config
from iris_oek.load import connect

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def config():
    return Config.read(FIXTURES / "config.json")


@pytest.fixture
def collection():
    return json.loads((FIXTURES / "parcels.geojson").read_text())


@pytest.fixture
def database():
    dsn = os.environ.get("TEST_DATABASE_URL")
    admin = os.environ.get("TEST_ADMIN_DATABASE_URL")
    if not dsn or not admin:
        pytest.skip(
            "Isolated PostGIS test DSNs not set; use docker compose --profile test run --rm tests"
        )
    with connect(admin) as connection:
        connection.execute(
            "TRUNCATE iris_staging.harvest_issues, iris_staging.harvest_runs, iris_staging.compensation_sites"
        )
    yield dsn
