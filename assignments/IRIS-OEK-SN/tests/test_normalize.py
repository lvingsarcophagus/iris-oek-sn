import copy
import math
from dataclasses import replace

import pytest
from shapely.geometry import Polygon, mapping

from iris_oek.config import Config
from iris_oek.normalize import Reject, normalize, number, process


def convert(feature, config, collection, **kwargs):
    return normalize(
        feature,
        config,
        collection["crs"]["properties"]["name"],
        collection["source_namespace"],
        **kwargs,
    )


def test_outcomes_and_original_provenance(config, collection):
    records, counts, issues = process(
        collection["features"],
        config,
        collection["crs"]["properties"]["name"],
        collection["source_namespace"],
        fixture=True,
    )
    assert counts == dict(received=12, accepted=4, repaired=1, rejected=7, duplicate=1)
    assert counts["received"] == counts["accepted"] + counts["rejected"] + counts["duplicate"]
    assert len([i for i in issues if i["outcome"] == "rejected"]) == 7
    first, missing, repaired, unknown = records
    assert first.municipality == "Dresden Stadt"
    assert first.cadastre == "Altstadt I"
    assert first.compensation_status == "available"
    assert first.source_crs.endswith("25833")
    assert first.source_properties == collection["features"][0]["properties"]
    assert first.source_geometry == collection["features"][0]["geometry"]
    assert first.geometry.geom_type == "MultiPolygon"
    assert first.area_m2 == pytest.approx(first.geometry.area)
    assert first.area_m2 == pytest.approx(10000, rel=0.02)
    assert all(r.geometry.is_valid and r.state_code == "SN" for r in records)
    assert missing.municipality is missing.compensation_status is missing.ecological_credit is None
    assert any(flag.startswith("geometry_repaired") for flag in repaired.quality_flags)
    assert repaired.source_geometry == collection["features"][2]["geometry"]
    assert unknown.source_status == "nicht_verifiziert" and unknown.compensation_status is None
    assert unknown.ecological_credit == 12.5


def test_stable_key_and_content_changes(config, collection):
    feature = collection["features"][0]
    original = convert(feature, config, collection)
    changed = copy.deepcopy(feature)
    changed["properties"]["gemeinde"] = "Dresden"
    update = convert(changed, config, collection)
    assert original.site_id == update.site_id
    assert original.content_hash != update.content_hash
    assert original.site_id != convert(feature, config, collection, fixture=True).site_id
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        process([feature, changed], config, original.source_crs, original.source_namespace)


@pytest.mark.parametrize("value", [True, -1, "NaN", "1.234,56", "-1", "1e6", math.inf])
def test_ambiguous_and_nonfinite_numbers(value):
    with pytest.raises(Reject):
        number(value)


def test_units_and_missing_mapping(config, collection):
    feature = copy.deepcopy(collection["features"][0])
    feature["properties"]["flaeche"] = "1,0"
    record = convert(feature, replace(config, area_unit="ha"), collection)
    assert record.source_area_m2 == 10_000
    unmapped = convert(feature, Config(), collection)
    assert unmapped.municipality is unmapped.source_area_m2 is unmapped.compensation_status is None
    assert unmapped.source_id == feature["id"]
    with pytest.raises(ValueError, match="verified"):
        replace(config, area_unit=None)


def test_holes_multipart_3d_and_missing_state(config, collection):
    feature = copy.deepcopy(collection["features"][0])
    outer = [(410000, 5650000), (410100, 5650000), (410100, 5650100), (410000, 5650100)]
    hole = [(410020, 5650020), (410040, 5650020), (410040, 5650040), (410020, 5650040)]
    feature["geometry"] = mapping(Polygon(outer, [hole]))
    record = convert(feature, config, collection)
    assert len(record.geometry.geoms[0].interiors) == 1
    assert record.area_m2 == pytest.approx(9600, rel=0.02)
    feature["geometry"] = {
        "type": "MultiPolygon",
        "coordinates": [feature["geometry"]["coordinates"]],
    }
    assert convert(feature, config, collection).geometry.is_valid
    feature["geometry"] = mapping(Polygon([(x, y, 3) for x, y in outer]))
    with pytest.raises(Reject, match="2D"):
        convert(feature, config, collection)
    feature = copy.deepcopy(collection["features"][0])
    feature["properties"].pop("land")
    with pytest.raises(Reject, match="State"):
        convert(feature, config, collection)
