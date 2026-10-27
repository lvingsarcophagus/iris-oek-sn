"""CLI: discovery is read-only; database loading always requires --load."""

import argparse
import hashlib
import json
import os
import sys
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd

from iris_oek.config import Config
from iris_oek.load import initialize, load
from iris_oek.normalize import process
from iris_oek.wfs import SourceError, WFS


def write_json(path, value):
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="IRIS-OEK-SN staging harvester")
    parser.add_argument("command", choices=["discover", "run", "init-db"])
    parser.add_argument("--config", type=Path, default=Path("config.example.json"))
    parser.add_argument("--fixture", type=Path, help="Explicitly synthetic fixture collection")
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument(
        "--load", action="store_true", help="Commit to the configured staging database"
    )
    args = parser.parse_args(argv)
    run_id = str(uuid.uuid4())
    directory = args.output / run_id
    directory.mkdir(parents=True, exist_ok=False)
    report = {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "started",
        "is_fixture": bool(args.fixture),
        "command": args.command,
    }
    client = None
    try:
        config = Config.read(args.config)
        report["config"] = asdict(config)  # Config has no credential fields.
        if args.command == "init-db":
            initialize(os.environ["DATABASE_URL"])
            report["status"] = "initialized"
        elif args.command == "discover":
            client = WFS(config, directory / "source")
            report["discovery"] = asdict(client.discover())
            report["status"] = "discovered"
        else:
            if args.fixture:
                data = args.fixture.read_bytes()
                (directory / "fixture.json").write_bytes(data)
                collection = json.loads(
                    data,
                    parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")),
                )
                if (
                    collection.get("fixture") is not True
                    or collection.get("type") != "FeatureCollection"
                ):
                    raise ValueError("Fixture must declare fixture=true and type=FeatureCollection")
                source_crs = collection["crs"]["properties"]["name"]
                namespace = collection["source_namespace"]
                report["input_sha256"] = hashlib.sha256(data).hexdigest()
                features = collection["features"]
            else:
                client = WFS(config, directory / "source")
                discovery = client.discover()
                report["discovery"] = asdict(discovery)
                source_crs, namespace = discovery.source_crs, discovery.namespace
                features = client.features(discovery)
            records, counts, issues = process(
                features, config, source_crs, namespace, bool(args.fixture)
            )
            report["counts"] = counts
            write_json(directory / "issues.json", issues)
            report["status"] = "validated"
            report["load"] = {"inserted": 0, "updated": 0, "unchanged": 0}
            if args.load:
                report["load"] = load(os.environ["DATABASE_URL"], records, report, issues)
                report["status"] = "loaded"
            # GeoJSON export is always RFC 7946 WGS84. DB working geometry is EPSG:25832.
            frame = (
                gpd.GeoDataFrame(
                    [
                        {
                            "site_id": r.site_id,
                            "state_code": r.state_code,
                            "source_id": r.source_id,
                            "area_m2": r.area_m2,
                            "is_fixture": r.is_fixture,
                            "geometry": r.geometry,
                        }
                        for r in records
                    ],
                    geometry="geometry",
                    crs=25832,
                )
                if records
                else None
            )
            export = (
                json.loads(frame.to_crs(4326).to_json(drop_id=True))
                if frame is not None
                else {"type": "FeatureCollection", "features": []}
            )
            write_json(directory / "sites.geojson", export)
    except Exception as exc:
        report["status"] = "failed"
        # Never serialize DB connection exceptions: DSNs can contain credentials.
        report["error"] = (
            str(exc) if isinstance(exc, (SourceError, ValueError)) else type(exc).__name__
        )
        print(f"Failed: {report['error']}; report: {directory / 'report.json'}", file=sys.stderr)
        return 1
    finally:
        if client:
            client.close()
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_json(directory / "report.json", report)
    print(
        json.dumps({"status": report["status"], "report": str(directory / "report.json")}, indent=2)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
