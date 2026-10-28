import os
import uuid

import pytest

from iris_oek.load import connect, initialize
from tests.conftest import FIXTURES


@pytest.mark.integration
def test_v1_migration_preserves_rows_and_is_idempotent(database):
    admin = os.environ["TEST_ADMIN_DATABASE_URL"]
    with connect(admin) as connection:
        connection.execute(
            "DROP TABLE iris_staging.harvest_issues, iris_staging.harvest_runs, iris_staging.compensation_sites"
        )
        connection.execute((FIXTURES / "schema_v1.sql").read_text())
        connection.execute(
            """INSERT INTO iris_staging.compensation_sites
            (site_id,state_code,source_id,area_m2,source_crs,source_crs_wkt,source_geometry,
             source_properties,geom,quality_flags,source_endpoint,source_layer,source_namespace,
             is_fixture,content_hash,last_run_id)
            VALUES ('preserved','SN','old',100,'EPSG:25832','preserved','{}','{}',
             ST_Multi(ST_MakeEnvelope(500000,5600000,500010,5600010,25832)), '[]',
             'https://geoportal.sachsen.de/wfs/oekokonto','sn_oekokonto_flurstuecke',
             'synthetic-migration-test',true,'old',%s)""",
            (str(uuid.uuid4()),),
        )
    initialize(admin)
    initialize(admin)
    with connect(admin) as connection:
        assert connection.execute(
            "SELECT site_id,source_kind,source_domain FROM iris_staging.compensation_sites"
        ).fetchall() == [("preserved", "fixture", "compensation_parcels")]
        connection.execute(
            "GRANT SELECT,INSERT,UPDATE ON iris_staging.compensation_sites TO iris_harvester"
        )
        connection.execute(
            "GRANT SELECT,INSERT ON iris_staging.harvest_runs,iris_staging.harvest_issues TO iris_harvester"
        )
