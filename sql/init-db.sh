#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=harvester_password="$HARVESTER_PASSWORD" <<'SQL'
CREATE EXTENSION IF NOT EXISTS postgis;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
\i /schema.sql
SELECT format('CREATE ROLE iris_harvester LOGIN PASSWORD %L', :'harvester_password') \gexec
GRANT USAGE ON SCHEMA iris_staging, public TO iris_harvester;
GRANT SELECT, INSERT, UPDATE ON iris_staging.compensation_sites TO iris_harvester;
GRANT SELECT, INSERT ON iris_staging.harvest_runs, iris_staging.harvest_issues TO iris_harvester;
SQL
