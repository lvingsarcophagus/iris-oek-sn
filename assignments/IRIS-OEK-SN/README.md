# IRIS-OEK-SN — Saxony compensation parcels

TASK 058 / Wave 3. Python 3.11+, WFS → GeoPandas/Shapely → PostGIS.
Target: **`iris_staging.compensation_sites`**, keyed by `(site_id, state_code)`.
This independent subproject is based on upstream commit
`76d448eb8953488e55bc4c3ba193629d534a7bb8`; it does not invoke the base application's pipelines.

For an in-depth explanation of the design and code, read
[PROJECT_WALKTHROUGH.md](PROJECT_WALKTHROUGH.md).

**Live access limitation:** the assignment's [GetCapabilities endpoint](https://geoportal.sachsen.de/wfs/oekokonto?service=WFS&request=GetCapabilities)
returned HTTP 404 on 2026-10-27. No live layer, namespace, attributes, permissions,
CRS, pagination support, or registered sites could be verified. The submitted
demonstration uses explicitly **synthetic fixtures**, as permitted by the brief.
The field names in `tests/fixtures/` are test assumptions, not an observed Saxony schema.
See [evidence](evidence/endpoint-check.md) and [quality report](QUALITY_REPORT.md).

**Real-data alternative:** the user-approved LISt KISS/KoKa-Nat public GeoPackage
now runs through the same normalizer and staging loader. It is labelled
`compensation_measures`, with its actual endpoint/layer, licence and attribution.
See [alternative source/mapping](ALTERNATIVE_SOURCE.md) and
[requirements audit](REQUIREMENTS_AUDIT.md).

```bash
# After configuring Docker credentials as below:
mkdir -p output data
docker compose run --build --rm harvester run --config config.list.example.json --load
```

Existing demo databases need the [explicit migration](ALTERNATIVE_SOURCE.md#existing-database-migration).

## Run locally (no database needed)

Run commands from the directory containing this README
(`assignments/IRIS-OEK-SN/` in the base repository).
Use Python 3.11+ and uv 0.9.5, or the pip alternative below.

```bash
uv sync --locked --extra test --python 3.11
uv run --locked iris-oek run --config tests/fixtures/config.json \
  --fixture tests/fixtures/parcels.geojson
uv run --locked pytest -q -m 'not integration'
uv run --locked ruff check .
uv run --locked ruff format --check .
```

Without uv:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install --require-hashes -r requirements.lock
pip install --no-deps -e .
iris-oek run --config tests/fixtures/config.json --fixture tests/fixtures/parcels.geojson
pytest -q -m 'not integration'
```

`requirements.lock` is a hashed export including test dependencies. Pip installs
the pinned build backend `hatchling==1.27.0` and `editables==0.5` in an isolated build environment.
`uv.lock` pins the complete runtime/test dependency graph. Docker uses that lock.

Each invocation creates `output/<run UUID>/report.json`. Successful normalization
also writes `issues.json` and an RFC 7946 WGS84 `sites.geojson`. Fixture inputs are
copied with a SHA-256; live response bodies, request parameters, HTTP status and
SHA-256 hashes are archived under `source/`. No credentials belong in configuration
or reports. Examples are checked into [examples/](examples/).

## Isolated Docker/PostGIS demonstration

The Compose project creates its own database and volume, publishes no ports and
uses a restricted loader role. PostgreSQL/PostGIS initialization is performed by a
separate migration role. No external database or production credentials are needed.

```bash
# Creates ignored local credentials; do not commit .env.
python3 - <<'PY'
from pathlib import Path
import os, secrets
p = Path('.env')
p.write_text('POSTGRES_PASSWORD=' + secrets.token_hex(24) + '\n'
             'HARVESTER_PASSWORD=' + secrets.token_hex(24) + '\n'
             'LOCAL_UID=' + str(os.getuid()) + '\nLOCAL_GID=' + str(os.getgid()) + '\n')
p.chmod(0o600)
PY
mkdir -p output
docker compose up -d --wait db
docker compose build
docker compose run --rm harvester run --config tests/fixtures/config.json \
  --fixture tests/fixtures/parcels.geojson --load
docker compose run --rm harvester run --config tests/fixtures/config.json \
  --fixture tests/fixtures/parcels.geojson --load
docker compose exec -T db psql -U iris_migrator -d iris_oek_demo < sql/validate.sql
```

Expected: first run inserts 4 sites; second inserts 0 and leaves 4 unchanged.
Reports contain 12 received, 4 accepted, 1 repaired (a subset of accepted),
7 rejected and 1 duplicate on both runs. `--load` is required for database writes.
Compose's default command validates fixtures without loading.

Run all tests, including real PostGIS transactions, CRS/geometry assertions,
idempotence, updates, rollback and privilege checks:

```bash
docker compose --profile test run --build --rm tests
```

**Integration tests truncate only this demo database's three staging tables.**
Do not point test DSNs at a shared database. Outside Compose, tests require
`TEST_DATABASE_URL` (restricted loader) and `TEST_ADMIN_DATABASE_URL` (isolated
test database migration role); otherwise integration tests are reported as skipped.
Stop this project using `docker compose down`; add `-v` only to delete its demo data.
The loader has no schema-creation or public-table-write permission. `init-db` is an
optional migration command for a separate isolated database with PostGIS already
installed; supply a migration DSN through `DATABASE_URL`.

## Source discovery and mapping

```bash
uv run --locked iris-oek discover --config config.example.json
```

Discovery archives capabilities, XSD and a machine-readable summary. The supplied
endpoint currently returns 404. Live harvesting requires a reviewed XSD hash,
verified attribute mappings/units, WFS 2.0 paging/sorting, a unique ID property,
GeoJSON with an explicit CRS, and numeric before/after hits counts. Missing live
attributes remain unmapped. HTTP errors, repeated IDs, changed counts, truncation
and mismatched CRS fail before loading; there is no automatic fixture fallback.

| Target | Mapping |
|---|---|
| `site_id`, `state_code` | Stable hash of source namespace/layer/ID plus fixture/live scope; `SN` |
| `municipality`, `cadastre` | Explicit mapped text fields, Unicode NFC and whitespace normalization |
| status | Reviewed value lookup; unknown values stay NULL with original text retained |
| `area_m2`, `source_area_m2` | EPSG:25832 geometry area; separately retained source area with verified unit |
| credits | Explicit source field/unit, otherwise NULL; no estimate from area/status |
| geometry/provenance | Valid MultiPolygon in EPSG:25832; original CRS/WKT, geometry JSON, properties, source identity and run metadata retained |

See [MAPPING.md](MAPPING.md) for the full attribute table, synthetic field names,
repair policy, pagination controls and live enablement procedure.

## Assumptions and limitations

Fixtures demonstrate behavior; they cannot prove registered-site membership or
provider permissions. The coarse Saxony envelope catches gross location errors
but is not an authoritative state boundary. Only wholly polygonal `make_valid`
results are accepted; collapsed/mixed repairs are rejected. Null optional values
stay null, and all repairs/rejections/unknown statuses are reported.

The supplied staging DDL is a new explicit contract. Existing incompatible tables
need a reviewed migration. Upserts and successful audit logs share one transaction;
SQL failures roll back the complete load and are reported locally. Identical replay
updates only last-seen metadata. Disappeared/rejected sites are retained for review;
there are no inferred deletions. SQL targets only `iris_staging`.

The client deliberately supports WFS 2.0 with JSON and a simple named XSD feature
type; unsupported versions/formats/schemas fail closed. Offset paging cannot detect
every same-count concurrent edit, so a quiescent source/snapshot is needed for strict
consistency. Rights and actual source schema of the original WFS remain unverified;
the alternative's reviewed public-download licence and schema are documented separately.
[QUALITY_REPORT.md](QUALITY_REPORT.md) records the observed outcomes and acceptance
limits. The provider named in the brief is LfULG Sachsen; synthetic exports are not
provider data.
