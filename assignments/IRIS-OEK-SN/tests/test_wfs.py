import copy
import json
from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
import responses

from iris_oek import ENDPOINT
from iris_oek.wfs import SourceError, WFS, xml
from tests.conftest import FIXTURES


def params(request):
    return {k: v[0] for k, v in parse_qs(urlsplit(request.url).query).items()}


def discovery_response(request):
    operation = params(request)["request"]
    return (
        200,
        {"Content-Type": "application/xml"},
        (
            FIXTURES / ("capabilities.xml" if operation == "GetCapabilities" else "schema.xsd")
        ).read_text(),
    )


@responses.activate
def test_discovery(config, tmp_path):
    responses.add_callback(responses.GET, ENDPOINT, callback=discovery_response)
    client = WFS(config, tmp_path, sleep=lambda _: None)
    found = client.discover()
    assert found.type_name == "sn:sn_oekokonto_flurstuecke"
    assert found.namespace == "urn:iris:synthetic:saxony"
    assert found.paging and found.sorting and found.count_default == 2
    assert found.schema_fields["flaeche"] == "xsd:decimal"
    assert (tmp_path / "manifest.json").exists()
    assert len(client.manifest) == 2
    with pytest.raises(SourceError, match="Review"):
        list(client.features(found))


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "duplicate",
        "empty",
        "wrong_crs",
        "missing_crs",
        "count_change",
        "unknown_hits",
        "limit",
        "exception",
    ],
)
@responses.activate
def test_controlled_paging(config, collection, tmp_path, fault):
    features = [copy.deepcopy(collection["features"][i]) for i in [0, 1, 2]]
    hits = []
    offsets = []

    def callback(request):
        query = params(request)
        if query["request"] != "GetFeature":
            return discovery_response(request)
        if query.get("resultType") == "hits":
            hits.append(1)
            count = (
                "unknown"
                if fault == "unknown_hits"
                else 4
                if fault == "count_change" and len(hits) > 1
                else 3
            )
            return (
                200,
                {},
                f'<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" numberMatched="{count}"/>',
            )
        offset = int(query["startIndex"])
        offsets.append(offset)
        assert query["sortBy"] == "parcel_id A"
        assert query["srsName"].endswith("25833")
        page = {
            "type": "FeatureCollection",
            "numberMatched": 3,
            "crs": collection["crs"],
            "features": [features[0 if fault == "duplicate" else offset]],
        }
        if fault == "empty":
            page["features"] = []
        if fault == "wrong_crs":
            page["crs"] = {"properties": {"name": "EPSG:4326"}}
        if fault == "missing_crs":
            page.pop("crs")
        if fault == "exception":
            return 200, {}, "<ExceptionReport/>"
        return 200, {}, json.dumps(page)

    responses.add_callback(responses.GET, ENDPOINT, callback=callback)
    client = WFS(config, tmp_path, sleep=lambda _: None)
    found = client.discover()
    client.config = replace(
        config,
        reviewed_schema_sha256=found.schema_sha256,
        max_pages=1 if fault == "limit" else 1000,
    )
    if fault:
        with pytest.raises(SourceError):
            list(client.features(found))
    else:
        assert list(client.features(found)) == features
        assert offsets == [0, 1, 2]  # server cap below requested count
        assert len(hits) == 2


@responses.activate
def test_retry_and_access_restrictions(config, tmp_path):
    sleeps = []
    client = WFS(config, tmp_path, sleep=sleeps.append)
    responses.get(ENDPOINT, status=503, headers={"Retry-After": "9999"})
    responses.get(ENDPOINT, body="ok", status=200)
    assert client.request("GetCapabilities") == b"ok"
    assert 30 in sleeps
    responses.get(ENDPOINT, status=403)
    before = len(responses.calls)
    with pytest.raises(SourceError, match="403"):
        client.request("GetCapabilities")
    assert len(responses.calls) == before + 1


@responses.activate
def test_timeout_size_and_redirect(config, tmp_path):
    client = WFS(replace(config, retries=1), tmp_path, sleep=lambda _: None)
    responses.get(ENDPOINT, body=requests.Timeout())
    with pytest.raises(SourceError, match="bounded retries"):
        client.request("GetCapabilities")
    assert len(responses.calls) == 2
    responses.reset()
    responses.get(ENDPOINT, status=302, headers={"Location": "https://example.com"})
    with pytest.raises(SourceError, match="302"):
        client.request("GetCapabilities")
    assert len(responses.calls) == 1
    responses.reset()
    client.config = replace(config, max_response_bytes=1024)
    responses.get(ENDPOINT, body="x" * 2000)
    with pytest.raises(SourceError, match="byte limit"):
        client.request("GetCapabilities")


def test_unsafe_xml():
    with pytest.raises(SourceError):
        xml(b'<!DOCTYPE a [<!ENTITY x "boom">]><a>&x;</a>')


@pytest.mark.parametrize("change", ["layer", "ambiguous", "version", "namespace"])
@responses.activate
def test_discovery_rejects_wrong_contract(config, tmp_path, change):
    capabilities = (FIXTURES / "capabilities.xml").read_text()
    schema = (FIXTURES / "schema.xsd").read_text()
    if change == "layer":
        capabilities = capabilities.replace("sn_oekokonto_flurstuecke", "other")
    elif change == "version":
        capabilities = capabilities.replace('version="2.0.0"', 'version="1.1.0"')
    elif change == "namespace":
        schema = schema.replace(
            'targetNamespace="urn:iris:synthetic:saxony"', 'targetNamespace="urn:other"'
        )
    else:
        feature = capabilities.split("<wfs:FeatureType>")[1].split("</wfs:FeatureType>")[0]
        capabilities = capabilities.replace(
            "</wfs:FeatureTypeList>",
            f"<wfs:FeatureType>{feature}</wfs:FeatureType></wfs:FeatureTypeList>",
        )
    responses.get(ENDPOINT, body=capabilities)
    responses.get(ENDPOINT, body=schema)
    with pytest.raises(SourceError):
        WFS(config, tmp_path).discover()
