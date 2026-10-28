-- Explicit staging-only migration from the original submission. Run via init-db
-- with an isolated database migration role; existing site identities are preserved.
ALTER TABLE iris_staging.compensation_sites
    ADD COLUMN IF NOT EXISTS source_kind text NOT NULL DEFAULT 'wfs',
    ADD COLUMN IF NOT EXISTS source_domain text NOT NULL DEFAULT 'compensation_parcels',
    ADD COLUMN IF NOT EXISTS source_license text,
    ADD COLUMN IF NOT EXISTS source_attribution text;
ALTER TABLE iris_staging.compensation_sites
    DROP CONSTRAINT IF EXISTS compensation_sites_source_endpoint_check,
    DROP CONSTRAINT IF EXISTS compensation_sites_source_layer_check,
    DROP CONSTRAINT IF EXISTS compensation_sites_source_profile_check;
UPDATE iris_staging.compensation_sites SET source_kind='fixture'
WHERE is_fixture AND source_kind='wfs';
ALTER TABLE iris_staging.compensation_sites
    ADD CONSTRAINT compensation_sites_source_profile_check CHECK (
        (source_kind IN ('wfs','fixture')
         AND source_endpoint='https://geoportal.sachsen.de/wfs/oekokonto'
         AND source_layer='sn_oekokonto_flurstuecke'
         AND source_domain='compensation_parcels'
         AND (source_kind='fixture')=is_fixture)
        OR
        (source_kind='list_geopackage' AND NOT is_fixture
         AND source_endpoint='https://www.list.smwa.sachsen.de/inspire/download/DE-SN-SBV_INSPIRE_Downloadservice_Kompensationsflaechen.zip'
         AND source_layer='Kompensationsmassnahmen_Flaechen'
         AND source_domain='compensation_measures'
         AND source_license IS NOT NULL AND source_license='https://www.govdata.de/dl-de/by-2-0'
         AND source_attribution IS NOT NULL AND source_attribution='Quelle: Kompensationsmaßnahmen-Informationssystem Freistaat Sachsen')
    );
