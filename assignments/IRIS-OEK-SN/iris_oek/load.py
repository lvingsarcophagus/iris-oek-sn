"""One transaction, explicit staging names, no production application imports."""

from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

SCHEMA = Path(__file__).resolve().parent / "sql" / "schema.sql"


def connect(dsn):
    return psycopg.connect(
        dsn,
        connect_timeout=10,
        options="-c search_path=pg_catalog,public -c statement_timeout=60000 -c lock_timeout=10000",
    )


def initialize(dsn):
    with connect(dsn) as connection:
        connection.execute(SCHEMA.read_text())
        connection.execute(SCHEMA.with_name("002_list_source.sql").read_text())


def load(dsn, records, report, issues):
    outcomes = dict(inserted=0, updated=0, unchanged=0)
    # Every identifier interpolated into SQL is derived from our static Record type.
    columns = [key for key in records[0].payload() if key != "geometry"] if records else []
    columns.append("content_hash")
    with connect(dsn) as connection:
        # Serialize runs of this harvester, including empty snapshots.
        connection.execute("SELECT pg_advisory_xact_lock(580058)")
        for record in records:
            previous = connection.execute(
                "SELECT content_hash FROM iris_staging.compensation_sites WHERE site_id=%s AND state_code=%s FOR UPDATE",
                (record.site_id, record.state_code),
            ).fetchone()
            outcome = (
                "inserted"
                if previous is None
                else "unchanged"
                if previous[0] == record.content_hash
                else "updated"
            )
            values = vars(record).copy()
            values.pop("geometry")
            for field in ("source_geometry", "source_properties", "quality_flags"):
                values[field] = Jsonb(values[field])
            values["wkb"] = record.geometry.wkb
            values["run_id"] = report["run_id"]
            placeholders = ", ".join(f"%({key})s" for key in columns)
            updates = ", ".join(
                f"{key}=EXCLUDED.{key}" for key in columns if key not in {"site_id", "state_code"}
            )
            if outcome == "unchanged":
                connection.execute(
                    "UPDATE iris_staging.compensation_sites SET last_seen=now(), last_run_id=%s WHERE site_id=%s AND state_code=%s",
                    (report["run_id"], record.site_id, record.state_code),
                )
            else:
                connection.execute(
                    f"INSERT INTO iris_staging.compensation_sites ({', '.join(columns)}, geom, last_run_id) "
                    f"VALUES ({placeholders}, ST_GeomFromWKB(%(wkb)s,25832), %(run_id)s) "
                    f"ON CONFLICT (site_id,state_code) DO UPDATE SET {updates}, geom=EXCLUDED.geom, "
                    "updated_at=now(), last_seen=now(), last_run_id=EXCLUDED.last_run_id",
                    values,
                )
            outcomes[outcome] += 1
        final_report = {**report, "load": outcomes, "status": "loaded"}
        connection.execute(
            "INSERT INTO iris_staging.harvest_runs (run_id,report) VALUES (%s,%s)",
            (report["run_id"], Jsonb(final_report)),
        )
        for index, issue in enumerate(issues):
            connection.execute(
                "INSERT INTO iris_staging.harvest_issues VALUES (%s,%s,%s)",
                (report["run_id"], index, Jsonb(issue)),
            )
    return outcomes
