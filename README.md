# IRIS-OEK-SN — Saxony compensation parcel WFS harvester

**TASK 058 / Wave 3.** The assignment is at the repository root. This Python 3.11
pipeline discovers a WFS layer, retrieves records with controlled pagination,
normalizes attributes, validates/repairs polygons, preserves original CRS/provenance,
and performs transactional, idempotent upserts into
**`iris_staging.compensation_sites`**, with working geometry in **EPSG:25832**.

**Live-source limitation:** the exact assignment endpoint returned HTTP 404 again
on **29 October 2026 (Europe/Vilnius)**, with and without a WFS version parameter.
The brief explicitly permits a **fixture-based demonstrator** when live access is
unavailable; that is this submission's reproducible run path. WFS discovery/schema/
pagination are implemented and tested through representative HTTP mocks. No other
dataset is substituted. Exact live-layer schema/permissions and registered parcel
or eco-account membership remain unverified.
[Current endpoint evidence](evidence/original-wfs-recheck-2026-10-29.json) ·
[Requirement audit](REQUIREMENTS_AUDIT.md) · [Submission note](SUBMISSION_NOTE.md).

## Reviewer quick start

Requires **Git**, **Docker with Compose**, and **Python 3** for local credential
generation. Docker supplies Python 3.11 and all application dependencies. Commands
work in Linux, macOS or WSL; use `sudo` for Docker if required by your Linux account.

### 1. Clone and enter the repository

```bash
git clone https://github.com/lvingsarcophagus/iris-oek-sn.git
cd iris-oek-sn
```

Run subsequent commands from this root directory. With the ZIP, enter the extracted
directory containing this README and skip cloning.

### 2. Generate local credentials and start isolated PostGIS

```bash
python3 - <<'PY'
from pathlib import Path
import os, secrets
p = Path('.env')
if not p.exists():
    p.write_text('POSTGRES_PASSWORD=' + secrets.token_hex(24) + '\n'
                 'HARVESTER_PASSWORD=' + secrets.token_hex(24) + '\n'
                 'LOCAL_UID=' + str(os.getuid()) + '\nLOCAL_GID=' + str(os.getgid()) + '\n')
    p.chmod(0o600)
    print('Created local demo credentials.')
else:
    print('Using existing local demo credentials.')
PY
mkdir -p output
docker compose up -d --wait db
```

No external database account is needed. Compose project `iris-oek-sn-wfs` uses its
own volume, publishes no database ports and separates migration/runtime roles.
It does not reuse earlier demo projects' volumes. `.env` is local and ignored by Git.

### 3. Run the fixture harvester

```bash
docker compose run --build --rm harvester run \
  --config tests/fixtures/config.json \
  --fixture tests/fixtures/parcels.geojson --load --output output/fixture-first
```

On a fresh demo database: **12 received, 4 accepted/inserted, 7 rejected, 1 identical
duplicate**. One accepted polygon is repaired. These invented Dresden-area records
include deliberately malformed examples, are always marked `is_fixture=true`, and
make no claim to be real registered compensation sites. The command prints a report
location under:

```text
output/fixture-first/<run UUID>/
  report.json       # counts, loading outcomes and provenance
  issues.json       # rejection reasons and accepted-record quality flags
  sites.geojson     # WGS84 export, viewable in QGIS
  fixture.json      # exact input copy, with checksum in the report
```

### 4. Repeat the same input and inspect the database

```bash
docker compose run --rm harvester run \
  --config tests/fixtures/config.json \
  --fixture tests/fixtures/parcels.geojson --load --output output/fixture-second
docker compose exec -T db \
  psql -U iris_migrator -d iris_oek_demo < sql/validate.sql
```

Expected replay: **0 inserted, 0 updated, 4 unchanged**. SQL checks show four valid
fixture geometries in EPSG:25832 and no duplicate keys, plus a reproducible spatial
intersection query. [Saved examples](examples/).

### 5. Run automated checks

```bash
docker compose --profile test run --build --rm tests
```

Expected: **36 passed**, including **5 real PostGIS integration tests**. The remaining
31 tests cover HTTP-mocked WFS discovery/paging/limits/retries, fixture normalization,
geometry repair/rejection, missing attributes and CLI reports. Database tests check
upserts, stable-key updates, rollback, provenance and restricted permissions.
**Tests reset the demo staging tables**; rerun the harvester to restore demonstration
records. Use only isolated test resources.

Stop while retaining demo data with `docker compose down`; use
`docker compose down -v` only to delete this demo's database volume.

## Local Python and live-source discovery

With Python 3.11+ and uv 0.9.5, from the repository root:

```bash
uv sync --locked --extra test --python 3.11
uv run --locked iris-oek run --config tests/fixtures/config.json \
  --fixture tests/fixtures/parcels.geojson
uv run --locked pytest -q -m 'not integration'
uv run --locked iris-oek discover --config config.example.json
```

Expected: **31 non-database tests passed**. Without `--load`, the run validates and
exports without writing site tables. `uv.lock` pins the transitive dependency graph;
`requirements.lock` is the hashed pip alternative. Discovery saves capabilities,
DescribeFeatureType XSD and a machine-readable summary when available, or a failure
report. No substitute source or silent fixture fallback is used.

When the original service becomes available, review its advertised layer/namespace,
CRS, fields, units, status meanings, unique identifier and permissions. Pin the
reviewed schema hash and explicit mappings before live harvesting. The client
requires WFS 2.0, advertised JSON/paging/sorting, explicit response CRS and numeric
before/after hits counts. [Supported-source contract](MAPPING.md).

## Mapping and acceptance limits

| Target | Policy |
|---|---|
| Identity | Stable source namespace/layer/ID hash and fixture/live scope; `(site_id,state_code)` key |
| State/source | `SN`, exact assignment endpoint/layer and original source ID retained |
| Names/status/credits | Explicit verified mappings; absent optional values remain NULL with flags |
| Area | Measured in m² on EPSG:25832 geometry; source area retained separately only with a verified unit |
| Geometry/provenance | Valid positive-area 2D MultiPolygon; original CRS/WKT, geometry, attributes and input retained |
| Writes | Only `iris_staging`; one transaction for site upserts and successful audit logs |

Only wholly polygonal repairs are accepted; collapsed/mixed repairs are rejected.
Unclosed rings and nonfinite/3D coordinates are rejected, not silently rewritten.
The Saxony plausibility envelope is not authoritative boundary verification.
Disappeared/rejected previously loaded sites are retained for later review. WFS
paging cannot detect every same-count concurrent edit. Exact live schema, permissions
and cadastral/registered eco-account membership remain open until the service can
be verified. No restricted service is bypassed.

## Review guide

- [REQUIREMENTS_AUDIT.md](REQUIREMENTS_AUDIT.md): requirement-by-requirement assessment and gaps.
- [QUALITY_REPORT.md](QUALITY_REPORT.md): outcomes, errors, checks and limitations.
- [MAPPING.md](MAPPING.md): source/attribute mapping and supported protocol contract.
- [PROJECT_WALKTHROUGH.md](PROJECT_WALKTHROUGH.md): design and module explanation.
- [iris_oek/](iris_oek/), [tests/](tests/), [examples/](examples/): code, automated checks and saved artifacts.

Based on upstream commit `76d448eb8953488e55bc4c3ba193629d534a7bb8`; history is
retained. Unrelated upstream application files are removed from the current tree.
The root code and Docker configuration contain only this assignment; no core or
production runners are invoked.
