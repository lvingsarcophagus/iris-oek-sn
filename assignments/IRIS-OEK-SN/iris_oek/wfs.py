"""Bounded WFS 2 discovery and JSON paging. Unsupported services fail closed."""

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests
from defusedxml import ElementTree as ET
from pyproj import CRS

from iris_oek.config import Config

NS = {
    "wfs": "http://www.opengis.net/wfs/2.0",
    "ows": "http://www.opengis.net/ows/1.1",
    "xsd": "http://www.w3.org/2001/XMLSchema",
    "fes": "http://www.opengis.net/fes/2.0",
}


class SourceError(ValueError):
    pass


def xml(data):
    try:
        root = ET.fromstring(data)
    except Exception as exc:
        raise SourceError("Invalid or unsafe WFS XML") from exc
    if "Exception" in root.tag:
        raise SourceError("WFS exception: " + " ".join(root.itertext())[:500])
    return root


@dataclass
class Discovery:
    type_name: str
    namespace: str
    source_crs: str
    output_format: str | None
    paging: bool
    sorting: bool
    count_default: int | None
    schema_fields: dict
    schema_sha256: str
    access_constraints: list


class WFS:
    def __init__(self, config: Config, archive: Path, session=None, sleep=time.sleep):
        self.config = config
        self.archive = archive
        archive.mkdir(parents=True, exist_ok=True)
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "IRIS-OEK-SN/0.1 (candidate demonstrator)"})
        self.sleep = sleep
        self.manifest = []
        self.last_request = None

    def close(self):
        self.session.close()

    def request(self, operation, **params):
        config = self.config
        query = {"service": "WFS", "version": "2.0.0", "request": operation, **params}
        for attempt in range(config.retries + 1):
            if self.last_request is not None:
                self.sleep(
                    max(0, config.request_interval_seconds - (time.monotonic() - self.last_request))
                )
            self.last_request = time.monotonic()
            try:
                with self.session.get(
                    config.endpoint,
                    params=query,
                    timeout=config.timeout_seconds,
                    stream=True,
                    allow_redirects=False,
                ) as response:
                    data = bytearray()
                    for chunk in response.iter_content(64 * 1024):
                        data.extend(chunk)
                        if len(data) > config.max_response_bytes:
                            raise SourceError("Response exceeds configured byte limit")
                    name = f"{len(self.manifest):04d}-{operation}.body"
                    (self.archive / name).write_bytes(data)
                    self.manifest.append(
                        {
                            "params": query,
                            "retrieved_at": datetime.now(timezone.utc).isoformat(),
                            "status": response.status_code,
                            "file": name,
                            "sha256": hashlib.sha256(data).hexdigest(),
                        }
                    )
                    (self.archive / "manifest.json").write_text(json.dumps(self.manifest, indent=2))
                    if response.status_code in {429, 502, 503, 504} and attempt < config.retries:
                        delay = response.headers.get("Retry-After", "")
                        self.sleep(min(30, float(delay)) if delay.isdigit() else 2**attempt)
                        continue
                    if response.status_code != 200:
                        raise SourceError(f"{operation}: HTTP {response.status_code}; see archive")
                    return bytes(data)
            except (requests.Timeout, requests.ConnectionError) as exc:
                if attempt == config.retries:
                    raise SourceError(
                        f"{operation}: transport failure after bounded retries"
                    ) from exc
                self.sleep(2**attempt)
        raise SourceError("Request exhausted")

    def discover(self):
        data = self.request("GetCapabilities")
        root = xml(data)
        if root.tag != f"{{{NS['wfs']}}}WFS_Capabilities" or root.get("version") not in {
            "2.0.0",
            "2.0.2",
        }:
            raise SourceError("Only WFS 2.0 capabilities supported")
        candidates = []
        for feature in root.findall("wfs:FeatureTypeList/wfs:FeatureType", NS):
            name = feature.findtext("wfs:Name", namespaces=NS)
            if name and name.split(":")[-1] == self.config.layer:
                candidates.append((name, feature))
        if len(candidates) != 1:
            raise SourceError("Expected exactly one advertised compensation parcel layer")
        name, feature = candidates[0]
        namespaces = dict(
            item for _, item in ET.iterparse(__import__("io").BytesIO(data), events=["start-ns"])
        )
        namespace = (
            namespaces.get(name.split(":")[0], "") if ":" in name else namespaces.get("", "")
        )
        if not namespace:
            raise SourceError("Unresolved feature namespace")
        source_crs = feature.findtext("wfs:DefaultCRS", namespaces=NS)
        if not source_crs:
            raise SourceError("Layer has no DefaultCRS")
        CRS.from_user_input(source_crs)  # retain the advertised spelling in provenance
        constraints = {}
        for constraint in root.findall(".//ows:Constraint", NS):
            constraints[constraint.get("name")] = constraint.findtext(
                "ows:DefaultValue", namespaces=NS
            )
        formats = [
            v.text
            for v in root.findall(
                ".//ows:Operation[@name='GetFeature']/ows:Parameter[@name='outputFormat']//ows:Value",
                NS,
            )
        ]
        layer_formats = [v.text for v in feature.findall("wfs:OutputFormats/wfs:Format", NS)]
        formats = layer_formats or formats
        output_format = next(
            (
                f
                for f in formats
                if f and f.lower() in {"application/json", "application/geo+json", "json"}
            ),
            None,
        )
        schema_data = self.request("DescribeFeatureType", typeNames=name)
        schema = xml(schema_data)
        if schema.tag != f"{{{NS['xsd']}}}schema" or schema.get("targetNamespace") != namespace:
            raise SourceError("DescribeFeatureType namespace mismatch")
        declarations = schema.findall("xsd:element", NS)
        declaration = next((d for d in declarations if d.get("name") == self.config.layer), None)
        if declaration is None or not declaration.get("type"):
            raise SourceError("Expected named feature declaration in XSD")
        type_local = declaration.get("type").split(":")[-1]
        complex_type = schema.find(f"xsd:complexType[@name='{type_local}']", NS)
        if complex_type is None:
            raise SourceError("Imported/inline feature XSD types require explicit support")
        fields = {
            el.get("name"): el.get("type")
            for el in complex_type.findall(".//xsd:element", NS)
            if el.get("name")
        }
        result = Discovery(
            name,
            namespace,
            source_crs,
            output_format,
            constraints.get("ImplementsResultPaging", "").lower() == "true",
            constraints.get("ImplementsSorting", "").lower() == "true",
            int(constraints["CountDefault"])
            if str(constraints.get("CountDefault", "")).isdigit()
            else None,
            fields,
            hashlib.sha256(schema_data).hexdigest(),
            [v.text for v in root.findall(".//ows:AccessConstraints", NS) if v.text],
        )
        (self.archive / "discovery.json").write_text(json.dumps(asdict(result), indent=2))
        return result

    def count(self, discovery):
        root = xml(self.request("GetFeature", typeNames=discovery.type_name, resultType="hits"))
        value = root.get("numberMatched", "")
        if root.tag != f"{{{NS['wfs']}}}FeatureCollection" or not value.isdigit():
            raise SourceError("Numeric WFS hits count required to prove completeness")
        return int(value)

    def features(self, discovery):
        config = self.config
        if config.reviewed_schema_sha256 != discovery.schema_sha256:
            raise SourceError(
                "Review discovery and pin reviewed_schema_sha256 before live ingestion"
            )
        needed = set(config.fields.values()) | ({config.id_field} if config.id_field else set())
        if not needed <= discovery.schema_fields.keys():
            raise SourceError("Mapped attributes absent from DescribeFeatureType")
        if (
            not discovery.paging
            or not discovery.sorting
            or not config.id_field
            or not discovery.output_format
        ):
            raise SourceError(
                "Live mode needs advertised paging, sorting, JSON and a unique sort/id field"
            )
        total = self.count(discovery)
        offset = 0
        seen = set()
        for _ in range(config.max_pages):
            if offset == total:
                if self.count(discovery) != total:
                    raise SourceError("Source count changed during harvest")
                return
            count = min(config.page_size, total - offset)
            data = self.request(
                "GetFeature",
                typeNames=discovery.type_name,
                count=count,
                startIndex=offset,
                sortBy=f"{config.id_field} A",
                outputFormat=discovery.output_format,
                srsName=discovery.source_crs,
            )
            try:
                page = json.loads(
                    data, parse_constant=lambda _: (_ for _ in ()).throw(ValueError())
                )
            except (ValueError, UnicodeDecodeError) as exc:
                raise SourceError(
                    "Expected finite JSON; XML exception or malformed response"
                ) from exc
            if page.get("type") != "FeatureCollection" or not isinstance(
                page.get("features"), list
            ):
                raise SourceError("Invalid GeoJSON collection")
            crs = page.get("crs", {}).get("properties", {}).get("name")
            if not crs or CRS.from_user_input(crs) != CRS.from_user_input(discovery.source_crs):
                raise SourceError("Response CRS missing or differs from requested original CRS")
            features = page["features"]
            if not 0 < len(features) <= count:
                raise SourceError("Empty, oversized or prematurely truncated page")
            if "numberReturned" in page and int(page["numberReturned"]) != len(features):
                raise SourceError("numberReturned mismatch")
            if "numberMatched" in page and str(page["numberMatched"]) != str(total):
                raise SourceError("numberMatched changed")
            for feature in features:
                identifier = feature.get("properties", {}).get(config.id_field)
                if (
                    not isinstance(identifier, (str, int))
                    or isinstance(identifier, bool)
                    or not str(identifier).strip()
                ):
                    raise SourceError("Missing stable paging identifier")
                key = str(identifier)
                if key in seen:
                    raise SourceError(
                        "Repeated identifier: paging ignored, source changed or nonunique sort key"
                    )
                seen.add(key)
                yield feature
            offset += len(features)  # tolerate advertised server page caps
        if offset == total and self.count(discovery) == total:
            return
        raise SourceError("Page limit reached before verified complete acquisition")
