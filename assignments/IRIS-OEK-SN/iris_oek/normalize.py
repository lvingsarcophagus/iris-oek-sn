"""Conservative parcel normalization with unchanged source properties and geometry."""

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

import geopandas as gpd
import numpy as np
from pyproj import CRS
from shapely import get_coordinates, make_valid
from shapely.geometry import MultiPolygon, shape
from shapely.validation import explain_validity

from iris_oek import STATE
from iris_oek.config import Config

GEOGRAPHIC = CRS.from_epsg(4326)
PROJECTED = CRS.from_epsg(25832)


@lru_cache(maxsize=16)
def crs_details(name):
    crs = CRS.from_user_input(name)
    return crs, crs.to_wkt()


class Reject(ValueError):
    """A record cannot defensibly become a compensation polygon."""


def text(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise Reject("Expected text attribute")
    return " ".join(unicodedata.normalize("NFC", value).split()) or None


def number(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    # Deliberately reject thousands separators and ambiguous locale notation.
    if isinstance(value, bool) or not re.fullmatch(
        r"[+]?(?:\d+(?:[.,]\d+)?|[.,]\d+)", str(value).strip()
    ):
        raise Reject("Invalid/ambiguous nonnegative number")
    result = float(str(value).strip().replace(",", "."))
    if not math.isfinite(result):
        raise Reject("Nonfinite number")
    return result


@dataclass
class Record:
    site_id: str
    state_code: str
    source_id: str
    municipality: str | None
    cadastre: str | None
    compensation_status: str | None
    source_status: str | None
    area_m2: float
    source_area_m2: float | None
    ecological_credit: float | None
    credit_unit: str | None
    source_crs: str
    source_crs_wkt: str
    source_geometry: dict
    source_properties: dict
    geometry: object
    quality_flags: list
    source_endpoint: str
    source_layer: str
    source_namespace: str
    is_fixture: bool
    source_kind: str = "wfs"
    source_domain: str = "compensation_parcels"
    source_license: str | None = None
    source_attribution: str | None = None
    content_hash: str = ""

    def payload(self):
        values = vars(self).copy()
        values["geometry"] = self.geometry.wkb_hex
        values.pop("content_hash")
        return values


def normalize(feature, config: Config, source_crs: str, namespace: str, fixture=False):
    if not isinstance(feature, dict) or feature.get("type") != "Feature":
        raise Reject("Expected GeoJSON Feature")
    props = feature.get("properties")
    if not isinstance(props, dict):
        raise Reject("Missing source properties")
    identifier = props.get(config.id_field) if config.id_field else feature.get("id")
    if (
        isinstance(identifier, bool)
        or not isinstance(identifier, (str, int))
        or not str(identifier).strip()
    ):
        raise Reject("Missing stable source identifier")
    identifier = str(identifier)
    values = {target: props.get(source) for target, source in config.fields.items()}
    if "state" in values and str(values["state"]) not in config.state_values:
        raise Reject("State attribute is missing or not an explicitly allowed Saxony code")
    source_geometry = feature.get("geometry")
    if isinstance(source_geometry, dict) and source_geometry.get("type") in {
        "Polygon",
        "MultiPolygon",
    }:
        polygons = (
            [source_geometry.get("coordinates", [])]
            if source_geometry["type"] == "Polygon"
            else source_geometry.get("coordinates", [])
        )
        try:
            if any(
                len(ring) < 4 or ring[0] != ring[-1] for polygon in polygons for ring in polygon
            ):
                raise Reject("Source polygon ring is unclosed or too short")
        except (TypeError, IndexError) as exc:
            raise Reject("Malformed polygon rings") from exc
    try:
        original = shape(feature.get("geometry"))
    except Exception as exc:
        raise Reject("Missing or malformed geometry") from exc
    if original.is_empty or original.geom_type not in {"Polygon", "MultiPolygon"}:
        raise Reject("Empty or nonpolygon geometry")
    coordinates = get_coordinates(original, include_z=False)
    if original.has_z or original.has_m or not np.isfinite(coordinates).all():
        raise Reject("Only finite 2D source coordinates supported")
    crs, original_wkt = crs_details(source_crs)
    if crs.is_geographic and any(
        abs(v) > bound for v, bound in zip(original.bounds, [180, 90, 180, 90])
    ):
        raise Reject("Source coordinates outside geographic CRS range")
    flags = []
    if config.source_kind == "list_geopackage":
        flags.append("alternative_source_compensation_measures_not_cadastral_parcels")
    working = original
    if not working.is_valid:
        reason = explain_validity(working)
        working = make_valid(working, method="linework")
        if (
            working.is_empty
            or working.geom_type not in {"Polygon", "MultiPolygon"}
            or not working.is_valid
        ):
            raise Reject("Repair collapsed geometry or produced mixed dimensions")
        flags.append("geometry_repaired: " + reason)
    try:
        series = gpd.GeoSeries([working], crs=crs)
        geographic = series.to_crs(GEOGRAPHIC).iloc[0]
        # Gross-error screen only; this is not an authoritative administrative boundary.
        xmin, ymin, xmax, ymax = geographic.bounds
        if not (11.8 <= xmin <= xmax <= 15.1 and 50.1 <= ymin <= ymax <= 51.8):
            raise Reject("Geometry outside coarse Saxony plausibility envelope")
        working = series.to_crs(PROJECTED).iloc[0]
    except Reject:
        raise
    except Exception as exc:
        raise Reject("CRS transformation failed") from exc
    if working.geom_type == "Polygon":
        working = MultiPolygon([working])
    if (
        not working.is_valid
        or working.is_empty
        or not math.isfinite(working.area)
        or working.area <= 0
        or not np.isfinite(get_coordinates(working)).all()
    ):
        raise Reject("Invalid projected polygon or zero/nonfinite area")
    source_area = number(values.get("area"))
    if source_area is not None and config.area_unit == "ha":
        source_area *= 10_000
    if source_area is not None and abs(source_area - working.area) / working.area > 0.05:
        flags.append("source_area_differs_over_5_percent")
    source_status = text(values.get("status"))
    status = config.status_values.get(source_status) if source_status is not None else None
    if source_status is not None and status is None:
        flags.append("unmapped_status")
    for field in ("municipality", "cadastre", "status", "area", "credits"):
        if field not in values or values[field] is None or values[field] == "":
            flags.append("missing_" + field)
    identity = json.dumps(
        ["fixture" if fixture else "live", namespace, config.layer, identifier],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    site_id = "oek-sn:" + hashlib.sha256(identity.encode()).hexdigest()
    record = Record(
        site_id,
        STATE,
        identifier,
        text(values.get("municipality")),
        text(values.get("cadastre")),
        status,
        source_status,
        working.area,
        source_area,
        number(values.get("credits")),
        config.credit_unit if values.get("credits") is not None else None,
        source_crs,
        original_wkt,
        feature["geometry"],
        props,
        working,
        flags,
        config.endpoint,
        config.layer,
        namespace,
        fixture,
        source_kind="fixture" if fixture else config.source_kind,
        source_domain=config.profile.domain,
        source_license=config.profile.license_url,
        source_attribution=config.profile.attribution,
    )
    record.content_hash = hashlib.sha256(
        json.dumps(record.payload(), sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()
    return record


def process(features, config, source_crs, namespace, fixture=False):
    records, issues, seen = [], [], {}
    counts = dict(received=0, accepted=0, repaired=0, rejected=0, duplicate=0)
    for index, feature in enumerate(features):
        counts["received"] += 1
        try:
            record = normalize(feature, config, source_crs, namespace, fixture)
            if record.site_id in seen:
                if seen[record.site_id] != record.content_hash:
                    raise ValueError(
                        "Conflicting duplicate source identifier; aborting complete run"
                    )
                counts["duplicate"] += 1
                issues.append(
                    {
                        "index": index,
                        "source_id": record.source_id,
                        "outcome": "duplicate",
                        "reason": "Identical source identifier and content",
                    }
                )
                continue
            seen[record.site_id] = record.content_hash
            records.append(record)
            counts["accepted"] += 1
            counts["repaired"] += any(
                f.startswith("geometry_repaired") for f in record.quality_flags
            )
            if record.quality_flags:
                issues.append(
                    {
                        "index": index,
                        "source_id": record.source_id,
                        "outcome": "accepted_with_flags",
                        "reason": record.quality_flags,
                    }
                )
        except Reject as exc:
            counts["rejected"] += 1
            issues.append(
                {"index": index, "outcome": "rejected", "reason": str(exc), "feature": feature}
            )
    return records, counts, issues
