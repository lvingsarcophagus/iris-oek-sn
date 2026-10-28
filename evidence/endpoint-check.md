# Endpoint verification — 2026-10-27

Public, unauthenticated GET (no redirects followed):

```text
https://geoportal.sachsen.de/wfs/oekokonto?service=WFS&request=GetCapabilities
```

Observed HTTP **404 Not Found**, `Content-Type: text/html; charset=UTF-8`.
Response title: `Seite existiert nicht - Geoportal Sachsenatlas - sachsen.de`.
HTTP server date: `Tue, 27 Oct 2026 18:24:02 GMT`.
The 67,958-byte HTML response SHA-256 was:

```text
c40b0926a2707ec47f6367de0f9b5a7344ae73d19f9ede06c267cce75bd2749d
```

Headers are preserved in [endpoint-headers.txt](endpoint-headers.txt), with line
endings normalized to LF. The unrelated
portal HTML page is not redistributed. This result establishes endpoint unavailability
at the check time; it does not establish that the dataset never existed or is private.
No live DescribeFeatureType/GetFeature requests were made after discovery failed.
Capabilities/XSD fixtures in `tests/fixtures/` are synthetic, not cached live evidence.

Reproduce (a future result may differ):

```bash
curl --max-time 30 --retry 0 -sS -D endpoint-headers.txt \
  -o endpoint-response.html \
  'https://geoportal.sachsen.de/wfs/oekokonto?service=WFS&request=GetCapabilities'
sha256sum endpoint-response.html
```
