import copy
import uuid
from dataclasses import replace

import psycopg
import pytest

from iris_oek.load import connect, load
from iris_oek.normalize import process

pytestmark = pytest.mark.integration


def report():
    return {
        "run_id": str(uuid.uuid4()),
        "status": "validated",
        "counts": {"accepted": 4},
        "is_fixture": True,
    }


def rows(config, collection):
    return process(
        collection["features"],
        config,
        collection["crs"]["properties"]["name"],
        collection["source_namespace"],
        fixture=True,
    )


def test_real_postgis_idempotency_update_and_provenance(database, config, collection):
    records, counts, issues = rows(config, collection)
    first = report()
    first["counts"] = counts
    assert load(database, records, first, issues) == {"inserted": 4, "updated": 0, "unchanged": 0}
    with connect(database) as connection:
        snapshot = connection.execute(
            "SELECT site_id, updated_at FROM iris_staging.compensation_sites ORDER BY site_id"
        ).fetchall()
        assert (
            connection.execute(
                "SELECT count(*) FROM iris_staging.compensation_sites WHERE ST_IsValid(geom) AND ST_SRID(geom)=25832 AND ST_GeometryType(geom)='ST_MultiPolygon'"
            ).fetchone()[0]
            == 4
        )
        original = connection.execute(
            "SELECT source_geometry, source_properties, source_crs, area_m2, ST_Area(geom) FROM iris_staging.compensation_sites WHERE source_id='demo-001'"
        ).fetchone()
        assert original[0] == collection["features"][0]["geometry"]
        assert original[1] == collection["features"][0]["properties"]
        assert original[2].endswith("25833") and original[3] == pytest.approx(original[4])
    assert load(database, records, report(), issues) == {
        "inserted": 0,
        "updated": 0,
        "unchanged": 4,
    }
    with connect(database) as connection:
        assert (
            connection.execute(
                "SELECT site_id, updated_at FROM iris_staging.compensation_sites ORDER BY site_id"
            ).fetchall()
            == snapshot
        )
    changed = copy.deepcopy(collection)
    changed["features"][0]["properties"]["gemeinde"] = "Updated Municipality"
    changed["features"][3] = copy.deepcopy(changed["features"][0])
    updates, _, _ = rows(config, changed)
    assert load(database, updates, report(), []) == {"inserted": 0, "updated": 1, "unchanged": 3}
    with connect(database) as connection:
        assert (
            connection.execute("SELECT count(*) FROM iris_staging.compensation_sites").fetchone()[0]
            == 4
        )
        assert (
            connection.execute("SELECT count(*) FROM iris_staging.harvest_runs").fetchone()[0] == 3
        )
        assert (
            connection.execute("SELECT count(*) FROM iris_staging.harvest_issues").fetchone()[0]
            == len(issues) * 2
        )


def test_failure_rolls_back_sites_and_run_log(database, config, collection):
    records, _, _ = rows(config, collection)
    bad = replace(records[1], area_m2=-1)
    with pytest.raises(psycopg.errors.CheckViolation):
        load(database, [records[0], bad], report(), [])
    with connect(database) as connection:
        assert (
            connection.execute("SELECT count(*) FROM iris_staging.compensation_sites").fetchone()[0]
            == 0
        )
        assert (
            connection.execute("SELECT count(*) FROM iris_staging.harvest_runs").fetchone()[0] == 0
        )


def test_runtime_role_restricted_to_staging(database):
    with connect(database) as connection:
        superuser, create_db = connection.execute(
            "SELECT rolsuper, rolcreatedb FROM pg_roles WHERE rolname=current_user"
        ).fetchone()
        assert not superuser and not create_db
        assert not connection.execute(
            "SELECT has_schema_privilege(current_user,'public','CREATE')"
        ).fetchone()[0]
        assert not connection.execute(
            "SELECT has_database_privilege(current_user,current_database(),'CREATE')"
        ).fetchone()[0]
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("CREATE TABLE public.forbidden_write (id int)")


def test_empty_snapshot_records_audit_without_deleting(database, config, collection):
    records, _, _ = rows(config, collection)
    load(database, records, report(), [])
    assert load(database, [], report(), []) == {"inserted": 0, "updated": 0, "unchanged": 0}
    with connect(database) as connection:
        assert (
            connection.execute("SELECT count(*) FROM iris_staging.compensation_sites").fetchone()[0]
            == 4
        )
