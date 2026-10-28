# TASK 058 / IRIS-OEK-SN requirement audit — 2026-10-29

**Assessment:** implementation and deliverables are addressed through the brief's
explicitly permitted fixture demonstrator. The exact WFS still returns HTTP 404;
its actual schema, permissions and registered parcel/eco-account membership remain
unverified. Fixtures are always labelled synthetic and no alternate data is used.

| Requirement | Implementation / evidence |
|---|---|
| OGC WFS / GeoPandas / PostGIS | WFS 2.0 client, GeoPandas/Shapely normalization/projection, PostGIS staging loader |
| Discover advertised feature type and pagination | Capabilities/namespace resolution, XSD inspection, paging/sorting/format checks; verified with mocks, live blocked by 404 |
| Controlled polygon/ID retrieval | Timeouts, request spacing, bounded retry/bytes/pages, unique reviewed sort IDs, before/after hits and CRS checks |
| Normalize municipality/cadastre | Explicit fields, Unicode NFC/whitespace normalization; missing optional values stay NULL |
| Normalize status / area / available credits | Reviewed status lookup, raw value retained; projected m² area separate from verified-unit source area; credits require an explicit field/unit |
| Do not guess attributes | Default live mapping empty; reviewed schema hash required; unknown/missing fields reported |
| Validate and repair geometry defensibly | Reject nonpolygon/empty/nonfinite/3D/unclosed rings; only valid wholly polygonal repairs accepted, with reasons |
| Preserve original CRS; project to EPSG:25832 | Original string/WKT/geometry/properties/input retained; valid positive-area 25832 MultiPolygon enforced in DB |
| Write only iris_staging | Qualified staging SQL, isolated Compose project and restricted runtime role; no core/production runners |
| Stable site_id/state_code | Source namespace/layer/ID plus fixture/live scope; SN composite key and natural uniqueness constraint |
| Transactional idempotent upsert/error logging | One transaction/advisory lock, changed-key updates, unchanged last-seen refresh; rollback and local/DB reports tested |
| Source/attribute mappings and processing counts | MAPPING.md, report.json, issues.json; received=accepted+rejected+duplicate, repairs are an accepted subset |
| Spatial query or export | sql/validate.sql, WGS84 GeoJSON, stored sample/SQL reports |
| Python 3.11+ / pinned dependencies | Python 3.11 image, exact direct pins, transitive uv.lock and hashed requirements.lock |
| Example config / Dockerfile / Compose / no secrets | Root-level configuration and Docker setup; generated .env ignored, only .env.example tracked |
| README / provenance / assumptions / limitations | Root quick start, MAPPING.md, PROJECT_WALKTHROUGH.md, SUBMISSION_NOTE.md and this audit |
| Representative automated tests | 36 tests, including 5 actual PostGIS tests; HTTP mocks and synthetic fixtures; clean-clone README execution in CI |
| Short quality/error report | QUALITY_REPORT.md and saved rejected source examples/counts/first-replay/spatial proof |
| Correct state, layer and domain | Assignment state/layer are fixed, fixtures domain-labelled; exact real registered-site membership remains unverified until live access is restored |
| Reruns do not duplicate sites; quality issues reported | Fixture first load 4 inserts; replay 0 inserts/4 unchanged; PK and transactional tests; rejected/repaired/flagged outcomes reported |
| Verify permissions/schema; no restrictions bypassed | Live 404 is documented; no source facts or permissions invented and no alternate/restricted services used |

## Open exact-source acceptance items

1. Obtain a working/corrected endpoint for sn_oekokonto_flurstuecke and review its
   actual permissions, schema, CRS, stable identifier, units and status meanings.
2. Confirm cadastral parcel / registered eco-account membership from that source.
3. Add an authoritative boundary if strict per-record administrative membership is
   required; the current envelope detects gross errors only.
4. A different service version/format/XSD arrangement may require an adapter;
   strict snapshot consistency also requires a quiescent/snapshot-capable source.

These unavailable source facts cannot be established by synthetic tests. The
submission is an explicitly labelled, reproducible fixture-based WFS demonstrator
under the brief's stated fallback; it does not claim complete live acceptance.
