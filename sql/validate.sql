-- Reproducible quality and provenance checks. All rows should have SRID 25832.
SELECT state_code, source_layer, is_fixture, count(*) AS sites,
       count(*) FILTER (WHERE NOT ST_IsValid(geom) OR ST_IsEmpty(geom)) AS invalid,
       min(ST_SRID(geom)) AS min_srid, max(ST_SRID(geom)) AS max_srid,
       round(sum(area_m2)::numeric, 2) AS total_projected_m2
FROM iris_staging.compensation_sites
GROUP BY state_code, source_layer, is_fixture;

SELECT site_id, state_code, count(*)
FROM iris_staging.compensation_sites
GROUP BY site_id, state_code HAVING count(*) > 1;

-- Intersect a WGS84 window around the synthetic Dresden-area examples.
SELECT source_id, municipality, round(area_m2::numeric, 2) AS projected_m2,
       source_crs, quality_flags, ST_AsGeoJSON(ST_Transform(geom,4326)) AS geojson
FROM iris_staging.compensation_sites
WHERE geom && ST_Transform(ST_MakeEnvelope(13.6,50.9,14.0,51.2,4326),25832)
  AND ST_Intersects(geom, ST_Transform(ST_MakeEnvelope(13.6,50.9,14.0,51.2,4326),25832))
ORDER BY source_id;

SELECT report->'counts' AS processing, report->'load' AS loading
FROM iris_staging.harvest_runs ORDER BY completed_at DESC LIMIT 2;
