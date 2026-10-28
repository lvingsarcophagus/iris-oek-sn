# Quality/error report — TASK 058 / IRIS-OEK-SN

Updated 2026-10-28. The submission retains the allowed fixture WFS demonstrator and
adds the user-approved real Saxony LISt compensation-measure GeoPackage. The latter
is explicitly labelled as a different source/domain; it does not prove access to
`sn_oekokonto_flurstuecke` or registered cadastral eco-account membership.

## Full real-source result

| Outcome | Count |
|---|---:|
| Selected polygon records received | 41,452 |
| Accepted unique records | 41,434 |
| Repaired among accepted records | 51 |
| Rejected | 18 |
| Duplicates | 0 |
| First-load inserts | 41,434 |
| Replay inserts / updates / unchanged | 0 / 0 / 41,434 |

`41,452 = 41,434 + 18 + 0`; repaired is an accepted subset. The 13,745 line and
152,948 point records in separate layers are inventoried but intentionally outside
the selected polygon input, not counted as polygon rejections.

Fourteen records were rejected because repair collapsed their geometry or yielded
mixed dimensions. Four failed final projected validity/positive-area/finite checks.
[Rejected source IDs and exact reasons](examples/real-validation-summary.json)
identify all 18; full originals remain in the retained run archive/issues output.
No records were rejected by the coarse Saxony plausibility envelope.

The real export has no municipality, cadastre, source area or ecological-credit
fields. These remain NULL. `Massnahme_Stand=Bestand` is retained as raw source status;
availability/allocation is not inferred and normalized compensation status stays
NULL with a flag. Every accepted record is labelled as compensation-measure data.

## Acceptance evidence

- **43 automated tests passed**, including all **7 PostGIS integration tests**, with
  no skips. Python 3.11.14; lint and format checks passed. Tests include WFS mocks,
  original fixtures, public-adapter mocks, geometry repair, identity/update/replay,
  rollback, source-profile constraints, restricted roles and existing-schema migration.
- [Passing CI run](https://github.com/lvingsarcophagus/iris-oek-sn/actions/runs/40741513921)
  tested code commit `8d7246a03c984bf685f89f80c815aa1f2fee5cd4` and performed the
  full real-source first load and exact-archive replay in isolated PostGIS.
- [First report](examples/real-load-first-report.json),
  [replay report](examples/real-load-second-report.json), and
  [SQL output](examples/real-postgis-validation.txt) show 41,434 stored records,
  all valid in EPSG:25832, no duplicate keys, correct alternative source/domain,
  retained licence/attribution, and zero invented optional attributes.
- [Five-record GeoJSON sample](examples/real-sample.geojson),
  [source manifest/schema](evidence/list-source-manifest.json), and
  [source/mapping/licence](ALTERNATIVE_SOURCE.md) support review and reproduction.
  The full source ZIP/GeoPackage and full outputs are ignored rather than committed.
- Original synthetic demonstration: 12 received, 4 accepted (1 repaired), 7 rejected,
  1 identical duplicate. Its historical reports remain in examples/fixture-* and
  examples/load-*-report.json; synthetic data are always marked as fixtures.

## Remaining limitations

The [original WFS recheck](evidence/original-wfs-recheck-2026-10-28.json) still returned
HTTP 404. Its actual layer/schema, permissions and eco-account parcel membership
remain unverified. The public GeoPackage is a reviewed alternative, not that layer.
Its source licence is retained, and no restricted internal services are accessed.

The location envelope is not authoritative administrative-boundary validation.
WFS paging cannot detect every same-count concurrent edit. Unsupported WFS/XSD/format
arrangements stop explicitly. The alternative config pins the entire reviewed ZIP;
provider updates require review before changing its hash. Upserts retain disappeared
or rejected previously loaded sites for later stale-data review. PostgreSQL and local
files cannot share an atomic commit; committed DB run logs are authoritative.

[REQUIREMENTS_AUDIT.md](REQUIREMENTS_AUDIT.md) evaluates every requirement and states
which exact-source acceptance items remain open. The demonstrator satisfies the
brief's allowed unavailable-source route; complete live exact-source acceptance
cannot honestly be claimed.
