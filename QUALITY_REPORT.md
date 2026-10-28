# Quality/error report — TASK 058 / IRIS-OEK-SN

Updated 2026-10-29. The submission is a WFS harvester with the fixture-based
demonstration expressly allowed when the specified live source is unavailable.
Fixtures do not represent real registered offsets. No other dataset is substituted.

## Source limitation

The [current endpoint check](evidence/original-wfs-recheck-2026-10-29.json) returned
HTTP 404 / portal HTML for both canonical and explicit WFS 2.0 capabilities requests.
No live feature type, schema, permissions or registered-site membership could be
verified. No restrictions were bypassed; no real source fields or rights are invented.

## Fixture outcomes

| Outcome | Count |
|---|---:|
| Received | 12 |
| Accepted unique records | 4 |
| Repaired among accepted | 1 |
| Rejected | 7 |
| Identical duplicate | 1 |
| First inserts / replay inserts | 4 / 0 |
| Replay unchanged | 4 |

`12 = 4 + 7 + 1`; repaired is an accepted subset. Rejections cover a missing stable
ID, a point, a contradictory state code, an implausible location, null geometry,
collapsed polygon repair and mixed-dimensional polygon/line repair. Complete source
examples and reasons are in [fixture-issues.json](examples/fixture-issues.json).
Accepted edge cases include missing optional attributes and an unmapped status;
nulls remain null and the raw status is retained with a flag.

## Automated evidence

The current suite contains **36 tests: 31 non-database and 5 PostGIS integration
tests**. It covers WFS capabilities/XSD/paging through mocks; count/CRS/duplicate/
truncation checks; controlled retries/timeouts/byte limits; unsafe XML; Unicode,
units and nulls; geometry repair, holes/multipart, 3D and unclosed-ring rejection;
stable IDs; CLI exports; real PostGIS upserts/updates/rollback/provenance/permissions.

CI performs a fresh public clone into an empty directory and executes README steps
2–5 directly, including fixture first load/replay and all database tests. It checks
that only .env.example is tracked, local credentials are absent from tracked files,
and unrelated application files are absent. Current clean-clone evidence is saved
following the completed verification run. Historical [first](examples/load-first-report.json),
[replay](examples/load-second-report.json), [SQL output](examples/postgis-validation.txt)
and [GeoJSON](examples/fixture-sites.geojson) remain available for comparison.

## Acceptance limits

The exact original WFS and cadastral/eco-account domain remain unverified. The
coarse Saxony envelope detects gross location errors, not authoritative boundary
membership. WFS offset paging cannot detect every same-count concurrent edit, and
unsupported service versions/formats/XSD structures stop explicitly. No names,
statuses, area units or ecological credits are guessed. Previously loaded sites
are retained when absent/rejected in a later run; the feed is upsert-only.
PostgreSQL and local files cannot commit atomically together; committed database
run logs are authoritative if a later output write fails.

[REQUIREMENTS_AUDIT.md](REQUIREMENTS_AUDIT.md) explains which requirements are
implemented/tested and which exact-source acceptance facts remain open. The brief's
unavailable-source fixture route is used explicitly; complete live verification
is not claimed.
