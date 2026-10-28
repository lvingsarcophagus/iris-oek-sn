# Documented real-data alternative: LISt Saxony KISS / KoKa-Nat

User-approved on 2026-10-28. This input supplies **compensation-measure geometry**,
not a verified replacement for the assignment's cadastral parcel / eco-account WFS.
The original WFS route remains separate. There is no automatic fallback or relabelling
as `sn_oekokonto_flurstuecke`.

## Provenance and permission

- Publisher: LISt GmbH; dataset: Kompensationsmaßnahmen-Informationssystem /
  Kompensationsflächenkataster Sachsen (KISS / KoKa-Nat).
- [Official catalogue](https://data.gov.de/suche/daten/kompensationsmassnahmen-informationssystem-kompensationsflachenkataster-sachsen87dcd).
- [Official ZIP download](https://www.list.smwa.sachsen.de/inspire/download/DE-SN-SBV_INSPIRE_Downloadservice_Kompensationsflaechen.zip).
- [Metadata and public-download licence](https://www.geoportal.hessen.de/mapbender/geoportal/mod_readCSWResultsDetail.php?cat_id=2&mdtype=html&uuid=c2c6c5a8-dcb9-4ef7-a8a4-eed08fbe1d60).
- Listed licence: Datenlizenz Deutschland Namensnennung 2.0,
  https://www.govdata.de/dl-de/by-2-0.
- Source wording retained per row, report and export:
  `Quelle: Kompensationsmaßnahmen-Informationssystem Freistaat Sachsen`.

The catalogue labels the resource ESRI Shape; the actual ZIP contains a GeoPackage.
This public download is separate from restricted internal KISS/KoKa-Nat applications
or WFS services. Those restricted services are not accessed.

| Reviewed item | Observed 2026-10-28 |
|---|---|
| HTTP / ZIP size | 200, unauthenticated direct GET / 50,044,116 bytes |
| ZIP SHA-256 | `54173820d224ec39d8b3082810ddb4884703e4581e1ab38d64000b512a578693` |
| ZIP member | `DE-SN-SBV_INSPIRE_Downloadservice_Kompensationsflaechen.gpkg` |
| Uncompressed size / modified | 125,587,456 bytes / 2026-10-02 |
| Selected layer | `Kompensationsmassnahmen_Flaechen` |
| Selected records / distinct populated IDs | 41,452 / 41,452 |
| Declared geometry / original CRS | 2D MultiPolygon / EPSG:25833 |
| Excluded layers | 13,745 lines and 152,948 points; inventoried, not processed as polygon sites |

The polygon count is not a count of ecological projects, cadastral parcels, available
offsets or credits. Measures and sites can overlap.

## Actual attribute mapping

| Target | Actual source / policy |
|---|---|
| `source_id` | `ID`; storage FID `cid` is retained but never used as identity |
| `source_kind`, `source_domain` | `list_geopackage`, `compensation_measures` |
| Endpoint / layer | Actual ZIP URL and GeoPackage layer, enforced by DB constraints |
| `source_namespace` | `urn:iris:source:list-sn-kiss-koka-nat-public`; assigned by IRIS, not a claimed provider WFS namespace |
| `state_code` | `SN` from official Saxony source scope, plus coarse location validation |
| `source_status` | `Massnahme_Stand`; all reviewed values are `Bestand` |
| `compensation_status` | NULL + unmapped flag; inventory state does not establish availability/allocation |
| Municipality / cadastre / credits / credit unit / source area | NULL + missing flags: absent from this export |
| `area_m2` / `geom` | Measured area / valid MultiPolygon projected to EPSG:25832 |
| Original geometry / CRS | Pre-repair geometry JSON, EPSG:25833/WKT, original ZIP and GeoPackage retained |
| Licence / attribution | Retained explicitly per row, report and export |

Additional original attributes remain in `source_properties`: `Bauprojektbezeichnung`,
`Behoerdenkennzeichen`, `BKZ`, `Massnahme_Nr`, `Massnahme_Art`, `Teilmassnahme_Art`,
`Zielbiotoptyp`, `Zielbiotoptyp_Code`. None is guessed to be a missing municipality,
cadastre, allocation status or credit. Every accepted record also receives the flag
`alternative_source_compensation_measures_not_cadastral_parcels`.

## Run and replay

Configure local credentials as in README, then run from this directory:

```bash
mkdir -p output data
docker compose up -d --wait db
docker compose run --build --rm harvester run --config config.list.example.json --load
```

Omit `--load` for validation/export only. The adapter verifies the whole archive
checksum, safely extracts only the named member, inspects schema/CRS, reads bounded
batches, and invokes the shared normalizer and staging loader. Data are marked
`is_fixture=false` with distinct domain/provenance.

The example config pins the reviewed **whole snapshot**, including schema and records.
Provider updates stop ingestion before loading. Review the new schema, domain,
licence and outcomes before updating `reviewed_archive_sha256`.

Replay the exact downloaded input:

```bash
docker compose run --rm harvester run --config config.list.example.json \
  --archive output/REPLACE_WITH_RUN_UUID/source/download.zip --load
docker compose exec -T db psql -U iris_migrator -d iris_oek_demo < sql/validate_real.sql
```

Alternatively put a reviewed ZIP under ignored `data/` and pass
`--archive data/your-reviewed-file.zip`. The host data directory is mounted read-only.
Full archives and full exports are not committed; small evidence/sample files are.

## Existing database migration

New demo databases use updated DDL. Existing isolated demo databases need this
explicit staging-only migration, performed using the migration role:

```bash
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U iris_migrator -d iris_oek_demo \
  < iris_oek/sql/002_list_source.sql
```

It preserves existing rows/site keys, adds domain/licence metadata, and changes the
single-source checks to two allowlisted profiles. Fixture rows retain their fixture
classification. The runtime loader cannot migrate tables. `iris-oek init-db` also
applies the migration when given a migration DSN for an isolated staging database.

## Acceptance boundary

This supports real Saxony compensation-measure processing and repeatable staging
loads. It does not prove live access to the exact assignment WFS or that the source
records are cadastral eco-account parcels. See REQUIREMENTS_AUDIT.md for the explicit
remaining gaps and QUALITY_REPORT.md for actual full-snapshot outcomes.
