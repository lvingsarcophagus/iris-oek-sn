import json

import pytest
import responses

from iris_oek import ENDPOINT
from iris_oek.cli import main
from iris_oek.load import connect
from tests.conftest import FIXTURES


def test_fixture_cli(tmp_path):
    assert (
        main(
            [
                "run",
                "--config",
                str(FIXTURES / "config.json"),
                "--fixture",
                str(FIXTURES / "parcels.geojson"),
                "--output",
                str(tmp_path),
            ]
        )
        == 0
    )
    directory = next(tmp_path.iterdir())
    report = json.loads((directory / "report.json").read_text())
    assert report["status"] == "validated" and report["is_fixture"]
    assert report["counts"]["rejected"] == 7
    export = json.loads((directory / "sites.geojson").read_text())
    assert len(export["features"]) == 4
    assert "crs" not in export


@responses.activate
def test_live_failure_reports_without_database_or_export(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    responses.get(ENDPOINT, status=404, body="Not found")
    assert (
        main(["run", "--config", "config.example.json", "--load", "--output", str(tmp_path)]) == 1
    )
    directory = next(tmp_path.iterdir())
    report = json.loads((directory / "report.json").read_text())
    assert report["status"] == "failed" and "404" in report["error"]
    assert not (directory / "sites.geojson").exists()


@pytest.mark.integration
def test_cli_load_twice(database, tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database)
    arguments = [
        "run",
        "--config",
        str(FIXTURES / "config.json"),
        "--fixture",
        str(FIXTURES / "parcels.geojson"),
        "--output",
        str(tmp_path),
        "--load",
    ]
    assert main(arguments) == 0
    assert main(arguments) == 0
    reports = [json.loads(path.read_text()) for path in tmp_path.glob("*/report.json")]
    assert all(report["status"] == "loaded" for report in reports)
    assert sorted(report["load"]["inserted"] for report in reports) == [0, 4]
    assert sorted(report["load"]["unchanged"] for report in reports) == [0, 4]
    with connect(database) as connection:
        assert (
            connection.execute("SELECT count(*) FROM iris_staging.compensation_sites").fetchone()[0]
            == 4
        )
