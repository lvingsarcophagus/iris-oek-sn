import hashlib
import json
from dataclasses import replace
from pathlib import Path
from zipfile import ZipFile

import geopandas as gpd
import pytest
import responses
from shapely.geometry import MultiPolygon, shape

from iris_oek.cli import main
from iris_oek.config import Config
from iris_oek.geopackage import GeoPackageSource
from iris_oek.normalize import process
from iris_oek.sources import LIST_ENDPOINT, LIST_LAYER, LIST_MEMBER, LIST_NAMESPACE
from iris_oek.wfs import SourceError


@pytest.fixture
def public_snapshot(tmp_path, collection):
    """Synthetic GeoPackage matching the public adapter's shape, never provider data."""
    rows = []
    for i in [0, 1, 2, 8]:
        feature = collection["features"][i]
        geom = shape(feature["geometry"]) if feature["geometry"] else None
        if geom is not None and geom.geom_type == "Polygon":
            geom = MultiPolygon([geom])
        rows.append(
            {
                "ID": f"test-{i}",
                "Massnahme_Stand": "Bestand",
                "Bauprojektbezeichnung": "SYNTHETIC adapter test",
                "geometry": geom,
            }
        )
    path = tmp_path / LIST_MEMBER
    gpd.GeoDataFrame(rows, crs=25833).to_file(
        path, layer=LIST_LAYER, driver="GPKG", engine="pyogrio"
    )
    archive = tmp_path / "synthetic.zip"
    with ZipFile(archive, "w") as zipped:
        zipped.write(path, LIST_MEMBER)
    config = replace(
        Config.read(Path("config.list.example.json")),
        reviewed_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        page_size=2,
        request_interval_seconds=0,
    )
    return config, archive


def read(source, archive=None):
    manifest = source.acquire(archive)
    return process(source.features(), source.config, manifest["source_crs"], LIST_NAMESPACE)


@responses.activate
def test_download_and_replay_preserve_real_source_identity(public_snapshot, tmp_path):
    config, archive = public_snapshot
    responses.get(LIST_ENDPOINT, body=archive.read_bytes(), status=200)
    source = GeoPackageSource(config, tmp_path / "download")
    records, counts, issues = read(source)
    assert counts == dict(received=4, accepted=3, repaired=1, rejected=1, duplicate=0)
    assert source.manifest["selected_count"] == 4
    assert all(r.source_kind == "list_geopackage" and not r.is_fixture for r in records)
    assert all(
        r.source_domain == "compensation_measures" and r.source_layer == LIST_LAYER for r in records
    )
    assert all(
        r.source_endpoint == LIST_ENDPOINT and r.source_license and r.source_attribution
        for r in records
    )
    assert all(
        r.municipality is r.cadastre is r.ecological_credit is r.compensation_status is None
        for r in records
    )
    assert all(
        r.source_status == "Bestand" and "unmapped_status" in r.quality_flags for r in records
    )
    assert all(r.geometry.is_valid and r.source_crs == "EPSG:25833" for r in records)
    assert records[0].source_properties["Bauprojektbezeichnung"] == "SYNTHETIC adapter test"
    assert "cid" in records[0].source_properties
    other = GeoPackageSource(config, tmp_path / "replay")
    replay, replay_counts, _ = read(other, archive)
    assert [r.content_hash for r in records] == [r.content_hash for r in replay]
    assert replay_counts == counts
    assert other.manifest["input_mode"] == "replay_archive"
    assert len(responses.calls) == 1
    assert (tmp_path / "download" / "download.zip").read_bytes() == archive.read_bytes()
    assert any(i["outcome"] == "rejected" for i in issues)


def test_checksum_and_safe_archive_member(public_snapshot, tmp_path):
    config, archive = public_snapshot
    source = GeoPackageSource(
        replace(config, reviewed_archive_sha256="0" * 64), tmp_path / "mismatch"
    )
    with pytest.raises(SourceError, match="SHA-256"):
        source.acquire(archive)
    assert not (tmp_path / "mismatch" / "download.partial").exists()
    unsafe = tmp_path / "unsafe.zip"
    with ZipFile(unsafe, "w") as zipped:
        zipped.writestr("../outside.gpkg", "bad")
    config = replace(
        config, reviewed_archive_sha256=hashlib.sha256(unsafe.read_bytes()).hexdigest()
    )
    with pytest.raises(SourceError, match="member"):
        GeoPackageSource(config, tmp_path / "unsafe").acquire(unsafe)
    assert not (tmp_path / "outside.gpkg").exists()


def test_schema_crs_and_batch_checks(public_snapshot, tmp_path, monkeypatch):
    config, archive = public_snapshot
    with pytest.raises(SourceError, match="absent"):
        GeoPackageSource(
            replace(config, fields={"credits": "nonexistent"}, credit_unit="unverified"),
            tmp_path / "schema",
        ).acquire(archive)
    source = GeoPackageSource(config, tmp_path / "batches")
    source.acquire(archive)
    original = gpd.read_file
    monkeypatch.setattr(
        gpd, "read_file", lambda *args, **kwargs: original(*args, **kwargs).iloc[:0]
    )
    with pytest.raises(SourceError, match="incomplete"):
        list(source.features())
    monkeypatch.setattr(
        gpd, "read_file", lambda *args, **kwargs: original(*args, **kwargs).to_crs(4326)
    )
    with pytest.raises(SourceError, match="CRS"):
        list(source.features())


@responses.activate
def test_http_retry_restrictions_and_limits(public_snapshot, tmp_path):
    config, archive = public_snapshot
    responses.get(LIST_ENDPOINT, status=503)
    responses.get(LIST_ENDPOINT, status=200, body=archive.read_bytes())
    source = GeoPackageSource(config, tmp_path / "retried", sleep=lambda _: None)
    source.acquire()
    assert len(source.manifest["attempts"]) == 2
    responses.reset()
    responses.get(LIST_ENDPOINT, status=403)
    with pytest.raises(SourceError, match="403"):
        GeoPackageSource(config, tmp_path / "forbidden").acquire()
    assert len(responses.calls) == 1
    responses.reset()
    responses.get(LIST_ENDPOINT, status=302, headers={"Location": "https://example.com"})
    with pytest.raises(SourceError, match="302"):
        GeoPackageSource(config, tmp_path / "redirect").acquire()
    responses.reset()
    responses.get(LIST_ENDPOINT, status=200, body=b"x" * 2048)
    with pytest.raises(SourceError, match="byte limit"):
        GeoPackageSource(replace(config, max_response_bytes=1024), tmp_path / "oversized").acquire()


def test_cli_alternative_is_explicit_and_reports_truth(public_snapshot, tmp_path):
    config, archive = public_snapshot
    from dataclasses import asdict

    path = tmp_path / "config.json"
    path.write_text(json.dumps(asdict(config)))
    output = tmp_path / "output"
    assert (
        main(["run", "--config", str(path), "--archive", str(archive), "--output", str(output)])
        == 0
    )
    report_path = next(output.glob("*/report.json"))
    report = json.loads(report_path.read_text())
    assert not report["is_fixture"] and report["source_domain"] == "compensation_measures"
    assert report["source"]["source_namespace"] == LIST_NAMESPACE
    assert report["input_sha256"] == config.reviewed_archive_sha256
    export = json.loads(report_path.with_name("sites.geojson").read_text())
    assert all(
        f["properties"]["source_domain"] == "compensation_measures" for f in export["features"]
    )
    assert main(["run", "--archive", str(archive), "--output", str(tmp_path / "invalid")]) == 1


@pytest.mark.integration
def test_alternative_postgis_replay_and_source_constraints(
    public_snapshot, tmp_path, database, monkeypatch
):
    from dataclasses import asdict
    from iris_oek.load import connect, load
    import psycopg
    import uuid

    config, archive = public_snapshot
    path = tmp_path / "config.json"
    path.write_text(json.dumps(asdict(config)))
    monkeypatch.setenv("DATABASE_URL", database)
    args = [
        "run",
        "--config",
        str(path),
        "--archive",
        str(archive),
        "--output",
        str(tmp_path / "runs"),
        "--load",
    ]
    assert main(args) == 0 and main(args) == 0
    with connect(database) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM iris_staging.compensation_sites WHERE source_kind='list_geopackage' AND source_domain='compensation_measures' AND NOT is_fixture AND ST_SRID(geom)=25832 AND ST_IsValid(geom)"
            ).fetchone()[0]
            == 3
        )
        results = connection.execute(
            "SELECT report->'load' FROM iris_staging.harvest_runs ORDER BY completed_at"
        ).fetchall()
        assert results[0][0] == {"inserted": 3, "updated": 0, "unchanged": 0}
        assert results[1][0] == {"inserted": 0, "updated": 0, "unchanged": 3}
    records, _, _ = read(GeoPackageSource(config, tmp_path / "constraint"), archive)
    for bad in [
        replace(records[0], source_domain="compensation_parcels"),
        replace(records[0], source_license=None),
    ]:
        # A new content hash forces the loader to exercise the DB constraint.
        bad = replace(bad, content_hash="changed")
        with pytest.raises(psycopg.errors.CheckViolation):
            load(database, [bad], {"run_id": str(uuid.uuid4())}, [])
