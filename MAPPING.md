# Source discovery, attribute mapping and loading


```bash
uv run --locked iris-oek discover --config config.example.json
```

Discovery performs only `GetCapabilities` and `DescribeFeatureType`, retaining
responses and `discovery.json`. A 404/401/403 or OWS exception fails with an error
report, never a silent fixture fallback. Redirects are not followed. Only the
specified HTTPS endpoint and exact local layer name are permitted; an ambiguous
namespace is rejected. No alternative dataset or access restriction is bypassed.

Once the provider restores access:

1. Review advertised namespace, layer title/domain, permissions, DefaultCRS,
   fields, field units, stable unique identifier, and status value meanings.
2. Copy `config.example.json` to an untracked local config, set only verified
   mappings, and pin the downloaded XSD's `reviewed_schema_sha256`. Leave missing
   attributes unmapped; review `access_constraints` before retrieval.
3. Live harvesting requires WFS 2.0, advertised result paging and sorting, a
   unique mapped `id_field`, a numeric hits count, and advertised GeoJSON output.
   The server must report the requested original CRS in each JSON collection.
4. Run `iris-oek run --config <reviewed-config>` to validate/export first. Use
   `--load` only with the intended isolated staging `DATABASE_URL`.

The live client requests the advertised DefaultCRS, sorts ascending on the reviewed
unique identifier, uses `count`/`startIndex`, advances by actual records returned,
and checks hits before/after retrieval. It rejects repeated IDs, empty/truncated
pages, changed counts, mismatched CRS, unexpected formats and exhausted limits.
No site writes occur until complete acquisition and normalization finish. Offset
paging cannot detect every concurrent edit (e.g. delete+insert with unchanged count);
the service must be quiescent or supply a snapshot for a guaranteed consistent extract.

Defaults: 100 features/page, 1-second request spacing, 30-second socket timeout,
20 MB decompressed response cap, 1,000 pages and at most 2 retries. Only transport
failures and HTTP 429/502/503/504 are retried; backoff/Retry-After waits are bounded
to 30 seconds. Limits are configurable within enforced bounds. WFS 1.x, GML-only
responses, imported/inline feature XSD types and missing/unknown hits counts require
explicit future implementation; the client does not claim support for them.

## Attribute and geometry mapping

| Target | Rule / synthetic fixture source |
|---|---|
| `site_id` | `oek-sn:` + SHA-256 of JSON `[fixture/live, namespace, layer, source ID]`; preserves ID spelling, no row-number or geometry-derived IDs |
| `state_code` | `SN`, scoped to this exact source/layer; when mapped, source state must match explicitly allowed `SN` or `14` |
| `source_id` | Reviewed `id_field`; fixture uses `parcel_id`. A feature-level ID is supported for offline normalization only; live paging requires a unique property |
| `municipality`, `cadastre` | Explicit fields; fixture `gemeinde`, `gemarkung`. Unicode NFC and collapsed whitespace; spelling/case preserved |
| `compensation_status`, `source_status` | Exact reviewed lookup after whitespace normalization; fixture `status`. Unknown → normalized NULL + `unmapped_status`, raw retained |
| `area_m2` | Computed area of final EPSG:25832 polygon; always labelled geometric area |
| `source_area_m2` | Optional verified source field/unit; fixture `flaeche` in m²; `ha` converts ×10,000. Over 5% difference flagged |
| `ecological_credit`, `credit_unit` | Optional verified field and explicit unit; fixture `oekopunkte` / `synthetic_ecopoints`. No inference or conversion from area/status |
| `source_crs`, `source_crs_wkt` | Original advertised CRS string and full parsed WKT; synthetic fixture uses EPSG:25833 |
| `source_geometry`, `source_properties` | Original decoded JSON retained, including unrepaired coordinates and unknown attributes |
| `geom` | GeoPandas projection to EPSG:25832; valid, nonempty, positive-area 2D MultiPolygon, enforced again in PostGIS |
| provenance | Endpoint, exact layer, namespace, fixture flag, content hash, first/update/last-seen timestamps and last run UUID |

Null optional fields stay null and receive missing-field flags. Numeric parsing
accepts finite nonnegative numbers and a single dot/comma decimal separator; no
thousands separators, scientific notation, negative values or unit guesses.
The source area and computed area remain separate; source credit values never
become estimated ecological capacity.

Invalid polygon linework is repaired using Shapely `make_valid(method='linework')`.
Only wholly polygonal, valid, positive-area results are accepted, with the repair
reason logged. Collapsed or mixed-dimensional repairs are rejected; no discarded
line fragments, buffers, snapping, or convex hulls are silently substituted.
Holes and multipart shapes are retained. Original geometry is preserved as JSONB
because it can legitimately be invalid before repair. Byte-exact live responses
remain in the response archive.

All shapes must fit the coarse geographic envelope 11.8–15.1°E, 50.1–51.8°N.
This detects gross CRS/location errors; it **does not prove administrative membership**.
An authoritative Saxony boundary was unavailable and no boundary dataset is invented.
Confirmed state/domain membership therefore still requires restored source discovery
and review; fixture acceptance is evidence of implementation behavior only.

## Loading and operational behavior

SQL is explicitly qualified to `iris_staging`; there is no configurable target
schema, no call to upstream runners, and no write to `iris_core`. The supplied
[DDL](iris_oek/sql/schema.sql) defines the submission's staging contract. Existing
incompatible tables require a reviewed staging migration; they are not dropped or
silently altered. PostGIS must already be installed outside Docker initialization.

A single transaction and advisory lock cover all site upserts and successful run/
issue logs. Identical content only updates `last_seen`/`last_run_id`; changed content
updates the existing row. A failed SQL statement rolls the entire transaction back.
No deletions occur when a source feature disappears or is rejected, because this
harvester is an upsert feed, not an authoritative replacement snapshot. `last_seen`
supports later stale-data review. Conflicting duplicate IDs abort the run; identical
offline duplicates are counted once. Fixture keys are separate from live keys and
`is_fixture` makes test data easy to exclude.

Fatal acquisition/normalization/database failures return exit code 1 and write a
local report. Recoverable record rejections allow valid records to load, with issues
saved to JSON and `iris_staging.harvest_issues`; counts satisfy
`received = accepted + rejected + duplicate`. A successful exit can include rejected
records, so inspect counts. Failed transactions are logged locally, since their DB
audit rows would otherwise roll back. Local output and PostgreSQL cannot commit
atomically; database `harvest_runs` is authoritative for committed loads if an
output filesystem failure occurs after commit.

Protocol reference: [OGC WFS 2.0.2](https://docs.ogc.org/is/09-025r2/09-025r2.html).
Repair semantics: [Shapely make_valid](https://shapely.readthedocs.io/en/stable/reference/shapely.make_valid.html).
Provider identity in the brief: Sächsisches Landesamt für Umwelt, Landwirtschaft
und Geologie (LfULG). Dataset-specific rights and live attribution remain unverified;
the synthetic exports are not provider data and make no claim to registered offsets.
