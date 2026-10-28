"""Run on the isolated Compose DB after unit/integration tests, never a shared DSN.

Produces small reviewable artifacts; keeps the full source archive/exports in ignored output/.
"""

import json
import subprocess
from pathlib import Path


def compose(*arguments, **kwargs):
    return subprocess.run(
        ["docker", "compose", "--ansi", "never", *arguments], check=True, **kwargs
    )


def report(folder):
    files = list(Path(folder).glob("*/report.json"))
    if len(files) != 1:
        raise RuntimeError("Expected one fresh real-data run directory")
    return files[0], json.loads(files[0].read_text())


def main():
    evidence = Path("output/real-evidence")
    evidence.mkdir(parents=True, exist_ok=True)
    Path("data").mkdir(exist_ok=True)
    compose("build", "harvester")
    # This verification script resets only this isolated Compose demo's staging tables.
    # The actual harvester never truncates or deletes sites.
    compose(
        "exec",
        "-T",
        "db",
        "psql",
        "-X",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "iris_migrator",
        "-d",
        "iris_oek_demo",
        "-c",
        "TRUNCATE iris_staging.harvest_issues, iris_staging.harvest_runs, iris_staging.compensation_sites",
    )
    compose(
        "run",
        "--rm",
        "harvester",
        "run",
        "--config",
        "config.list.example.json",
        "--load",
        "--output",
        "output/real-first",
    )
    first_path, first = report("output/real-first")
    archive = first_path.parent / "source" / "download.zip"
    compose(
        "run",
        "--rm",
        "harvester",
        "run",
        "--config",
        "config.list.example.json",
        "--archive",
        str(archive),
        "--load",
        "--output",
        "output/real-second",
    )
    _, second = report("output/real-second")
    accepted = first["counts"]["accepted"]
    assert first["source"]["selected_count"] == first["counts"]["received"] == 41452
    assert accepted > 0 and first["load"] == {"inserted": accepted, "updated": 0, "unchanged": 0}
    assert second["load"] == {"inserted": 0, "updated": 0, "unchanged": accepted}
    assert first["input_sha256"] == second["input_sha256"]
    for result in [first, second]:
        assert result["status"] == "loaded" and not result["is_fixture"]
        assert result["source_domain"] == "compensation_measures"
        counts = result["counts"]
        assert counts["received"] == counts["accepted"] + counts["rejected"] + counts["duplicate"]
    query = """SELECT count(*),count(*) FILTER (WHERE ST_IsValid(geom) AND ST_SRID(geom)=25832),
        count(*) FILTER (WHERE municipality IS NOT NULL OR cadastre IS NOT NULL OR ecological_credit IS NOT NULL OR compensation_status IS NOT NULL),
        count(*) FILTER (WHERE source_domain='compensation_measures' AND NOT is_fixture AND source_license IS NOT NULL)
        FROM iris_staging.compensation_sites WHERE source_kind='list_geopackage'"""
    result = compose(
        "exec",
        "-T",
        "db",
        "psql",
        "-X",
        "-At",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "iris_migrator",
        "-d",
        "iris_oek_demo",
        "-c",
        query,
        capture_output=True,
        text=True,
    )
    stored, valid, guessed, provenance = map(int, result.stdout.strip().split("|"))
    assert stored == valid == provenance == accepted and guessed == 0
    with (
        Path("sql/validate_real.sql").open() as sql,
        (evidence / "postgis-validation.txt").open("w") as out,
    ):
        compose(
            "exec",
            "-T",
            "db",
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "iris_migrator",
            "-d",
            "iris_oek_demo",
            stdin=sql,
            stdout=out,
        )
    (evidence / "first-report.json").write_text(json.dumps(first, indent=2) + "\n")
    (evidence / "second-report.json").write_text(json.dumps(second, indent=2) + "\n")
    issues = json.loads(first_path.with_name("issues.json").read_text())
    from collections import Counter

    reasons = Counter()
    rejections = []
    for issue in issues:
        if issue["outcome"] == "rejected":
            reasons[issue["reason"]] += 1
            # Keep IDs/reasons in the submitted report; full originals remain in the run archive.
            properties = issue.get("feature", {}).get("properties", {})
            rejections.append({"source_id": properties.get("ID"), "reason": issue["reason"]})
    summary = {
        "rejected_reasons": dict(reasons),
        "rejected_records": rejections,
        "stored": stored,
        "valid_projected": valid,
        "guessed_attributes": guessed,
        "source_domain": "compensation_measures",
    }
    (evidence / "validation-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    collection = json.loads(first_path.with_name("sites.geojson").read_text())
    collection["features"] = collection["features"][:5]
    (evidence / "sample.geojson").write_text(json.dumps(collection, indent=2) + "\n")
    print(
        json.dumps(
            {"first": first["load"], "replay": second["load"], "validation": summary}, indent=2
        )
    )


if __name__ == "__main__":
    main()
