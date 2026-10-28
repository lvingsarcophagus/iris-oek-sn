# IRIS-OEK-SN — Saxony compensation data harvester

**TASK 058 / Wave 3.** A Python 3.11 pipeline that retrieves geographic records,
checks attributes and polygon geometry, and performs repeatable, transactional
upserts into **`iris_staging.compensation_sites`**. It preserves source data and
CRS, projects working geometry to **EPSG:25832**, and reports rejected/repaired data.

**Verified:** 43 automated tests passed, including 7 PostGIS integration tests.
The reviewed real-data run processed **41,452 polygons**, accepted **41,434**
(including **51 repairs**) and rejected **18**. Replaying the same input inserted
**zero new records**. [Passing CI and full real-data replay](https://github.com/lvingsarcophagus/iris-oek-sn/actions/runs/40741513921).

**Source limitation:** the assignment WFS returned HTTP 404 when rechecked on
2026-10-28. Its exact `sn_oekokonto_flurstuecke` layer remains unverified. The
recommended real-data demonstration uses the explicitly approved **LISt KISS /
KoKa-Nat public GeoPackage**, labelled `compensation_measures` with its actual
source/layer, licence and attribution. It does not establish cadastral parcel or
registered eco-account availability. The original WFS implementation and the
brief's permitted synthetic fixture demonstration remain available separately.
[Full requirement audit](assignments/IRIS-OEK-SN/REQUIREMENTS_AUDIT.md).

## Reviewer quick start — real data with Docker

Requires **Git**, **Docker with Compose**, and **Python 3** for generating local
credentials. Docker supplies Python 3.11 and all application dependencies. The
following commands work in Linux, macOS or WSL terminals. On Linux, prefix Docker
commands with `sudo` if your account requires it.

### 1. Clone and enter the assignment directory

```bash
git clone https://github.com/lvingsarcophagus/iris-oek-sn.git
cd iris-oek-sn/assignments/IRIS-OEK-SN
```

**Run every subsequent command from this directory.** If using the submission ZIP,
enter the extracted directory containing this README and skip cloning.

### 2. Create local credentials and start the isolated database

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
mkdir -p output data
docker compose up -d --wait db
```

No external database credentials are needed. Compose creates an isolated PostGIS
service and publishes no database ports. `.env` is ignored by Git. Existing demo
databases created with the original submission need the documented
[staging-only migration](assignments/IRIS-OEK-SN/ALTERNATIVE_SOURCE.md#existing-database-migration).

### 3. Build and run the real-data harvester

```bash
docker compose run --build --rm harvester run \
  --config config.list.example.json --load
```

The first run downloads/builds container images and retrieves the approximately
50 MB public source ZIP. It verifies the reviewed snapshot checksum, reads the
polygon layer, normalizes/validates it, and loads accepted records into staging.
Allow a few minutes for the initial build and processing.

On a fresh demo database, expect:

| Result | Expected count |
|---|---:|
| Polygon records received | 41,452 |
| Accepted / inserted | 41,434 |
| Repaired among accepted | 51 |
| Rejected with reasons | 18 |
| Duplicates | 0 |

The command prints the report location. Each run produces:

```text
output/<run UUID>/
  report.json       # processing counts, load results and source provenance
  issues.json       # quality flags and rejection reasons
  sites.geojson     # accepted geometry in WGS84, viewable in QGIS
  source/           # original input archive, GeoPackage and source manifest
```

The provider may update the download. If its hash changes, the harvester stops
before loading; review the new snapshot before updating the pinned configuration.
A [saved-archive replay](assignments/IRIS-OEK-SN/ALTERNATIVE_SOURCE.md#run-and-replay) avoids another download.

### 4. Verify repeatability and inspect the database

Run the same command again:

```bash
docker compose run --rm harvester run --config config.list.example.json --load
```

Expected: **0 inserted, 0 updated, 41,434 unchanged** for the reviewed input.
Then execute the supplied spatial/quality queries:

```bash
docker compose exec -T db \
  psql -U iris_migrator -d iris_oek_demo < sql/validate_real.sql
```

Expected: 41,434 alternative-source records, zero invalid geometries, SRID 25832,
zero duplicate keys, and zero inferred optional attributes. Saved
[first/replay reports and SQL output](assignments/IRIS-OEK-SN/QUALITY_REPORT.md#acceptance-evidence)
are included for comparison.

### 5. Run automated checks

```bash
docker compose --profile test run --build --rm tests
```

Expected: **43 passed**. Tests cover WFS discovery/pagination through HTTP mocks,
normalization, repair, source download/replay, real PostGIS upserts/rollback,
restricted permissions and migration. **Integration tests reset the demo staging
tables**, so run the real-data command again afterward if you want those records
back. Use only this isolated demo database for tests.

Stop the demo while retaining its data:

```bash
docker compose down
```

Use `docker compose down -v` only when you want to delete this demo's database volume.

## Small synthetic fixture demonstration

After the same Docker setup, use this command instead of the real-data command:

```bash
docker compose run --build --rm harvester run \
  --config tests/fixtures/config.json \
  --fixture tests/fixtures/parcels.geojson --load
```

Expected: 12 received, 4 accepted (including 1 repaired), 7 rejected and 1 identical
duplicate. On a fresh fixture input load, 4 are inserted; replay inserts 0 and leaves
4 unchanged. These invented Dresden-area examples deliberately include malformed
records and are always marked `is_fixture=true`, with keys separate from real data.

## Local Python option — no database required

With Python 3.11+ and uv 0.9.5, from the assignment directory:

```bash
uv sync --locked --extra test --python 3.11
uv run --locked iris-oek run --config tests/fixtures/config.json \
  --fixture tests/fixtures/parcels.geojson
uv run --locked pytest -q -m 'not integration'
```

Expected: 36 non-database tests passed. Omitting `--load` validates and exports
without writing site tables. `uv.lock` pins transitive dependencies;
`requirements.lock` provides a hashed pip alternative. For original WFS discovery:

```bash
uv run --locked iris-oek discover --config config.example.json
```

Discovery archives capabilities/XSD if available, or writes a failure report. It
never silently switches to fixtures or an alternative dataset.

## Mapping, guarantees and acceptance limits

| Target | Policy |
|---|---|
| Identity | Stable source namespace/layer/ID hash plus fixture/live scope; `(site_id,state_code)` key |
| State/source/domain | `SN`; actual endpoint/layer and distinct source domain retained |
| Names/status/credits | Explicit mappings only; absent values remain NULL with flags |
| Area | Computed in m² from EPSG:25832 geometry; source area retained separately only with verified units |
| Geometry | Valid, positive-area 2D MultiPolygon; original CRS/WKT and geometry retained |
| Writes | Only `iris_staging`; one transaction for upserts and successful audit logs |

The real alternative lacks municipality, cadastre, source-area and ecological-credit
fields. `Massnahme_Stand=Bestand` is kept as raw source status; allocation or
availability is not inferred. The source archive, licence and attribution are retained.

Only wholly polygonal repairs are accepted; collapsed/mixed repairs are rejected.
The coarse Saxony location envelope is not authoritative boundary verification.
Missing/disappeared sites are retained for later stale-data review. A changed
schema/snapshot requires review, and WFS offset paging cannot detect every concurrent
same-count edit. Exact original-layer permissions/schema and cadastral/eco-account
membership remain open acceptance items. No restricted services are bypassed.

## Review guide

| Document / file | What to inspect |
|---|---|
| [REQUIREMENTS_AUDIT.md](assignments/IRIS-OEK-SN/REQUIREMENTS_AUDIT.md) | Requirement-by-requirement assessment and remaining gaps |
| [QUALITY_REPORT.md](assignments/IRIS-OEK-SN/QUALITY_REPORT.md) | Full real-data results, rejected IDs, test evidence and limitations |
| [ALTERNATIVE_SOURCE.md](assignments/IRIS-OEK-SN/ALTERNATIVE_SOURCE.md) | Actual public source, licence, mapping, replay and existing-DB migration |
| [MAPPING.md](assignments/IRIS-OEK-SN/MAPPING.md) | Original WFS/fixture mapping and supported protocol contract |
| [PROJECT_WALKTHROUGH.md](assignments/IRIS-OEK-SN/PROJECT_WALKTHROUGH.md) | In-depth design and code explanation |
| [iris_oek/](assignments/IRIS-OEK-SN/iris_oek/) | WFS/GeoPackage input, normalization, CLI and staging loader |
| [tests/](assignments/IRIS-OEK-SN/tests/) | Representative fixtures, HTTP mocks and database checks |
| [examples/](assignments/IRIS-OEK-SN/examples/) | Saved reports, SQL validation and sample exports |

Based on upstream commit `76d448eb8953488e55bc4c3ba193629d534a7bb8`.
The assignment implementation is isolated under `assignments/IRIS-OEK-SN/`;
upstream application runners and production/core resources are not invoked.
