-- Apply using a migration role on an isolated staging database. PostGIS must exist.
CREATE SCHEMA IF NOT EXISTS iris_staging;

CREATE TABLE IF NOT EXISTS iris_staging.compensation_sites (
    site_id text NOT NULL,
    state_code text NOT NULL CHECK (state_code = 'SN'),
    source_id text NOT NULL,
    municipality text,
    cadastre text,
    compensation_status text,
    source_status text,
    area_m2 double precision NOT NULL CHECK (area_m2 > 0 AND area_m2 < 'Infinity'::float8),
    source_area_m2 double precision CHECK (source_area_m2 >= 0 AND source_area_m2 < 'Infinity'::float8),
    ecological_credit double precision CHECK (ecological_credit >= 0 AND ecological_credit < 'Infinity'::float8),
    credit_unit text,
    source_crs text NOT NULL,
    source_crs_wkt text NOT NULL,
    source_geometry jsonb NOT NULL,
    source_properties jsonb NOT NULL,
    geom geometry(MultiPolygon,25832) NOT NULL CHECK (ST_IsValid(geom) AND NOT ST_IsEmpty(geom)),
    quality_flags jsonb NOT NULL,
    source_endpoint text NOT NULL CHECK (source_endpoint = 'https://geoportal.sachsen.de/wfs/oekokonto'),
    source_layer text NOT NULL CHECK (source_layer = 'sn_oekokonto_flurstuecke'),
    source_namespace text NOT NULL,
    is_fixture boolean NOT NULL,
    content_hash text NOT NULL,
    first_seen timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    last_seen timestamptz NOT NULL DEFAULT now(),
    last_run_id uuid NOT NULL,
    PRIMARY KEY (site_id, state_code),
    UNIQUE (source_namespace, source_layer, source_id, state_code, is_fixture)
);
CREATE INDEX IF NOT EXISTS compensation_sites_geom_idx ON iris_staging.compensation_sites USING gist(geom);

CREATE TABLE IF NOT EXISTS iris_staging.harvest_runs (
    run_id uuid PRIMARY KEY,
    completed_at timestamptz NOT NULL DEFAULT now(),
    report jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS iris_staging.harvest_issues (
    run_id uuid NOT NULL REFERENCES iris_staging.harvest_runs(run_id),
    issue_number integer NOT NULL,
    detail jsonb NOT NULL,
    PRIMARY KEY (run_id, issue_number)
);
