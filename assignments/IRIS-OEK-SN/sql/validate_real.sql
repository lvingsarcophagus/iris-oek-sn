-- Alternative-source audit: these rows are compensation measures, not parcel/eco-account availability claims.
SELECT source_kind,source_domain,state_code,source_layer,count(*) AS records,
       count(*) FILTER (WHERE NOT ST_IsValid(geom) OR ST_IsEmpty(geom)) AS invalid,
       min(ST_SRID(geom)) AS min_srid,max(ST_SRID(geom)) AS max_srid,
       count(*) FILTER (WHERE municipality IS NOT NULL OR cadastre IS NOT NULL OR
           ecological_credit IS NOT NULL OR compensation_status IS NOT NULL) AS guessed_attributes
FROM iris_staging.compensation_sites
WHERE source_kind='list_geopackage'
GROUP BY source_kind,source_domain,state_code,source_layer;

SELECT site_id,state_code,count(*) FROM iris_staging.compensation_sites
GROUP BY site_id,state_code HAVING count(*)>1;

-- Geographic window around Dresden; transform the search window into the indexed working CRS.
SELECT source_id,source_status,source_crs,source_license,source_attribution,
       round(area_m2::numeric,2) AS area_m2,
       ST_AsGeoJSON(ST_Transform(geom,4326)) AS geometry
FROM iris_staging.compensation_sites
WHERE source_kind='list_geopackage'
  AND geom && ST_Transform(ST_MakeEnvelope(13.6,50.9,14.0,51.2,4326),25832)
  AND ST_Intersects(geom,ST_Transform(ST_MakeEnvelope(13.6,50.9,14.0,51.2,4326),25832))
ORDER BY source_id LIMIT 5;

SELECT report->'counts' AS processing,report->'load' AS loading
FROM iris_staging.harvest_runs ORDER BY completed_at DESC LIMIT 2;
