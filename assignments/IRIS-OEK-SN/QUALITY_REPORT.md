# Quality and error report

Assignment: IRIS-OEK-SN / TASK 058. Updated: 2026-10-28.

A user-approved real-data alternative now supplements the original fixture WFS
demonstration. Its complete-source local validation processed 41,452 polygons:
41,434 accepted (51 repaired), 18 rejected, zero duplicates. Fourteen rejections
were collapsed/mixed repairs and four failed final projected geometry/area checks.
PostGIS full-load/replay evidence is recorded separately after CI validation.
See [alternative provenance/mapping](ALTERNATIVE_SOURCE.md) and
[the requirement audit](REQUIREMENTS_AUDIT.md).

The results below headed fixture outcomes and the 35-test result describe the
original submission; they are retained as historical evidence, not the new totals.

## Source availability and acceptance boundary

The supplied public GetCapabilities URL returned **HTTP 404**, with a portal HTML
page rather than WFS XML. [Captured headers and response hash](evidence/endpoint-check.md)
document the observation. No sites were harvested from that WFS. The separately approved public GeoPackage
is labelled as an alternative compensation-measure source. Advertised feature type, source permissions, real attributes and
registered compensation-site membership remain unverified. The assignment explicitly
permits a fixture demonstrator when live access is unavailable.

The fixture namespace is `urn:iris:synthetic:saxony`; all exported examples carry
`is_fixture=true`. Its EPSG:25833 polygons are invented near Dresden. They do not
represent registered offsets, cadastral ownership, or usable ecological credits.

## Observed fixture outcomes

See the generated [report](examples/fixture-report.json), complete
[issues](examples/fixture-issues.json) and WGS84 [sample export](examples/fixture-sites.geojson).

| Outcome | Count | Interpretation |
|---|---:|---|
| Received | 12 | Input features including duplicate and bad records |
| Accepted, unique | 4 | Valid projected MultiPolygon records |
| Repaired | 1 | Subset of accepted: self-intersection repaired to polygonal parts |
| Rejected | 7 | Reasons below; source examples retained in issue log |
| Identical duplicate | 1 | Same stable identifier and content; no second site |

`12 = 4 + 7 + 1`. Repaired is an annotation of accepted, not a separate partition.

Rejected cases:

| Synthetic case | Reason |
|---|---|
| Missing source identifier | No stable key can be constructed |
| Point | Not a parcel polygon |
| `land=NW` | Contradicts allowed Saxony state codes |
| Geometry far north of Saxony | Fails coarse geographic plausibility check |
| Null geometry | No defensible parcel geometry |
| Collinear polygon | Repair collapses to lines |
| Polygon with a retraced spike | Repair yields mixed polygon/line dimensions; fragments are not discarded |

Accepted edge cases include null optional attributes and an unknown status. Nulls
stay null; unknown status retains the original string and receives a quality flag.
Area is measured from the projected working geometry. Credit fields are accepted
only when explicitly mapped with a unit; synthetic credit values make no claim
about the real provider's ecological accounting system.

## Automated evidence

**Result: 35 passed in 1.77 seconds**, Python 3.11.14, inside the built Docker
image with a real isolated PostGIS service. This includes all five integration
tests; none were skipped. Ruff lint and formatting checks also passed.

```bash
docker compose --profile test run --build --rm tests
# 35 passed
```

Tests exercise schema/namespace/layer discovery, WFS 2 paging with server-imposed
page caps, stable IDs, before/after hits, changed/unknown counts, repeated IDs,
truncation, missing/wrong CRS, XML exceptions, timeouts, bounded retry, HTTP 403,
redirect refusal, response byte caps and unsafe XML.

Normalization checks cover NFC/whitespace, nulls, explicit units, ambiguous numeric
formats, state mismatch, holes, multipart polygons, 3D rejection, repair/collapse,
retained raw geometry/properties, projected area, stable keys, unknown statuses and
conflicting duplicates. CLI tests verify reproducible fixture export and logged live
404 failure without database access or a fabricated export.

PostGIS tests use only the isolated Compose database. They check:

- First load inserts four sites; replay leaves four unchanged with no new sites.
- Changed source content updates one stable-key row.
- Stored geometry is valid MultiPolygon in EPSG:25832; area agrees with `ST_Area`.
- Original CRS, geometry and source attributes survive loading.
- A constraint violation on the second record rolls back the first insert and run audit.
- The runtime role has no superuser/database-creation/schema-creation privileges and
  cannot create a table in `public`.

Commands and full run instructions are in the [README](README.md).

The documented CLI was also run twice against a fresh disposable database, outside
pytest: [first load](examples/load-first-report.json) inserted 4; [replay](examples/load-second-report.json)
inserted 0 and left 4 unchanged. The executed [spatial validation output](examples/postgis-validation.txt)
shows four `SN` rows, zero invalid geometries, only SRID 25832, no duplicate keys,
four intersections in the sample window, and 50,125.15 m² total projected area.
The small difference from source-grid areas reflects projection into the required
UTM zone. Database [version](evidence/postgis-version.txt) and
[image digest](evidence/postgis-image.txt) are retained. Demo containers and their
temporary volume were removed after evidence capture.

## Remaining limitations

Live-data acceptance is conditional on provider access, schema/rights review and a
verified mapping; it cannot be concluded from synthetic tests. The approximate
Saxony envelope rejects gross errors but is not an authoritative state boundary.
Offset pagination lacks snapshot isolation and cannot prove consistency under every
same-count concurrent edit. Unsupported protocols/formats/XSD constructs fail closed.
No missing status, name, credit, area unit or ecological potential is guessed.

The staging DDL is an explicit submission contract; any existing target with a
different schema needs a reviewed migration. The loader performs upserts and retains
previously seen sites when later absent/rejected. It does not infer deletions or
availability from absence. Raw archives and rejected source properties can contain
provider data after future live use and should follow the provider's retention and
access conditions.
