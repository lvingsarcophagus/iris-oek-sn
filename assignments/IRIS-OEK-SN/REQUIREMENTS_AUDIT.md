# TASK 058 / IRIS-OEK-SN requirement audit — 2026-10-28

**Assessment:** implementation/delivery requirements are addressed, with executable
fixture and real alternative-source paths. Exact-source acceptance remains open:
the supplied WFS returns HTTP 404, so its advertised layer, permissions, real
schema and registered eco-account parcel membership cannot be verified. The brief
explicitly permits a fixture demonstrator when live access is unavailable. The
user additionally approved LISt compensation-measure geometry as a documented
alternative; that approval does not make it the requested cadastral parcel layer.

| Requirement | Status and evidence |
|---|---|
| Reproducible Saxony compensation/eco-account WFS harvester | Implemented WFS path + reproducible fixture fallback. A reviewed real Saxony compensation-measure GeoPackage path is additional evidence, not exact-WFS verification. |
| Discover advertised feature type and paging | Implemented/tested GetCapabilities, namespace resolution, DescribeFeatureType, paging/sorting/format checks, reviewed schema hash. Live original discovery is blocked by HTTP 404. |
| Controlled retrieval of polygons and source IDs | WFS request spacing/timeouts/retries/byte/page limits, before/after counts, unique sort IDs. Alternative uses checksum-pinned download, safe bounded extraction, schema/CRS checks, batches and original `ID` values. |
| Normalize municipality/cadastre | Implemented Unicode NFC/whitespace rules. Absent from the real alternative, so NULL + flags; fixture tests verify normalization. No inferred names. |
| Normalize compensation status | Explicit reviewed lookups; unknown values remain NULL with raw source text. Alternative `Bestand` is retained only as source inventory state, never guessed as available/allocated. |
| Area in square metres | Computed on valid EPSG:25832 working geometry. Source area is separately converted only with a verified unit; unavailable alternative source area remains NULL. |
| Available ecological-credit fields | Explicit mapping/unit support, tested. Alternative has no credit field/unit; both remain NULL. No capacity or points estimated. |
| Validate/repair geometries defensibly | Reject nonpolygon, empty, nonfinite, 3D/M and unclosed rings; accept only valid wholly polygonal make_valid results. Reject collapsed/mixed repairs, preserve originals, log outcomes. |
| Preserve original CRS; project to EPSG:25832 | Original CRS string/WKT and pre-repair geometry JSON retained; source archives retained. Alternative native EPSG:25833; working geometry constrained to valid 25832 MultiPolygon. |
| Write only to iris_staging | Explicit staging SQL and restricted runtime role; no upstream runner invocation or core writes. Migration is explicit and staging-only. |
| Stable site_id/state_code keys | SHA-256 identity uses namespace/layer/source ID and fixture/live scope; `state_code=SN`; actual source domain is stored separately. Composite PK/natural uniqueness constraints. |
| Transactional idempotent upserts | One transaction/advisory lock; changed rows update stable keys, unchanged content refreshes last-seen metadata. Rollback and repeated loads tested in PostGIS. |
| Error logging/outcome counts | Local reports/issues for failures and rejections; successful run/issues committed atomically. Received=accepted+rejected+duplicate; repairs are an accepted subset. |
| Source/attribute mappings | MAPPING.md for original fixture/WFS; ALTERNATIVE_SOURCE.md for actual GeoPackage, including missing fields, licence, assigned namespace and distinct domain. |
| Spatial query/sample export | sql/validate.sql, sql/validate_real.sql, WGS84 GeoJSON outputs and saved sample/evidence. |
| Python 3.11+, pinned dependencies | Python 3.11.14 verified; exact direct pins + transitive uv.lock and hashed requirements.lock. No new dependencies needed for the GeoPackage adapter. |
| Example config, Dockerfile, Compose; no secrets | Separate original/alternative configs, tested image and isolated PostGIS Compose project. Credentials generated locally; .env/data/archives excluded from Git and image context. |
| README with provenance/runs/schema/assumptions | README, MAPPING, ALTERNATIVE_SOURCE and PROJECT_WALKTHROUGH provide these; schema and explicit existing-demo migration included. |
| Representative automated tests | Original WFS/normalization/CLI/PostGIS tests plus GeoPackage download/replay/schema/CRS/archive/HTTP checks, source-domain DB constraints and v1 migration preservation. |
| Short quality/error report | QUALITY_REPORT.md, actual first/replay reports, rejection summary, source manifest, projected geometry SQL audit and small GeoJSON sample. |
| Correct state, layer and compensation-site domain | Alternative is genuinely published for Saxony compensation measures; actual layer/domain are retained. Coarse envelope is not authoritative state-boundary proof. Exact cadastral parcel/registered eco-account membership remains unverified. |
| Reruns do not duplicate sites; quality issues reported | Fixture proof retained; full real-snapshot first/replay and SQL evidence are required in CI before final acceptance of the alternative path. |
| Verify permissions; never bypass restrictions | Public archive/catalogue licence reviewed. Original 404 and access-denied responses stop; no restricted internal WFS access attempted. |

## Open acceptance items

1. Obtain a corrected/working endpoint for the exact `sn_oekokonto_flurstuecke`
   dataset, then verify permissions, CRS, source identifier and attribute meanings.
2. Confirm cadastral parcel / registered eco-account domain from actual source
   metadata; public compensation measures alone do not establish it.
3. For strict administrative membership, add a separately verified authoritative
   Saxony boundary; current screening catches gross errors only.
4. A WFS with a different version/format/schema arrangement may require a reviewed
   adapter. Offset pagination cannot guarantee snapshot consistency under all
   same-count concurrent edits.

No data processing can make these unavailable source facts true. The submission
should be described as an allowed fixture WFS demonstrator with a user-approved,
documented real Saxony compensation-measure alternative, rather than claiming that
every exact-source acceptance criterion has been proven.
