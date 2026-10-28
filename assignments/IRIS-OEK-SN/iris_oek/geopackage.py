"""Reviewed LISt public ZIP input. This is a separate source, never a WFS fallback."""

import hashlib
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import geopandas as gpd
import pandas as pd
import requests
from pyproj import CRS
from shapely.geometry import mapping

from iris_oek.sources import LIST_CATALOG, LIST_MEMBER, LIST_NAMESPACE
from iris_oek.wfs import SourceError

MAX_GPKG_BYTES = 200_000_000


class GeoPackageSource:
    def __init__(self, config, directory, session=None, sleep=time.sleep):
        if config.source_kind != "list_geopackage":
            raise SourceError("The GeoPackage adapter requires the explicit LISt profile")
        self.config = config
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.session = session or requests.Session()
        self.session.headers.update(
            {"User-Agent": "IRIS-OEK-SN/0.2 (documented public alternative)"}
        )
        self.sleep = sleep
        self.manifest = {
            "endpoint": config.endpoint,
            "layer": config.layer,
            "source_kind": config.source_kind,
            "source_domain": config.profile.domain,
            "source_namespace": LIST_NAMESPACE,
            "namespace_note": "Assigned by IRIS, not an advertised WFS namespace",
            "catalog": LIST_CATALOG,
            "license": config.profile.license_url,
            "attribution": config.profile.attribution,
            "attempts": [],
        }
        self.path = None

    def close(self):
        self.session.close()

    def save_manifest(self):
        (self.directory / "manifest.json").write_text(
            json.dumps(self.manifest, indent=2), encoding="utf-8"
        )

    def copy_bounded(self, chunks, target):
        digest, total = hashlib.sha256(), 0
        with target.open("wb") as out:
            for chunk in chunks:
                total += len(chunk)
                if total > self.config.max_response_bytes:
                    raise SourceError("Archive exceeds configured byte limit")
                digest.update(chunk)
                out.write(chunk)
        return digest.hexdigest(), total

    def acquire(self, archive=None):
        partial = self.directory / "download.partial"
        try:
            if archive is not None:
                with Path(archive).open("rb") as source:
                    digest, size = self.copy_bounded(iter(lambda: source.read(65536), b""), partial)
                self.manifest["input_mode"] = "replay_archive"
            else:
                self.manifest["input_mode"] = "public_download"
                for attempt in range(self.config.retries + 1):
                    try:
                        with self.session.get(
                            self.config.endpoint,
                            timeout=self.config.timeout_seconds,
                            stream=True,
                            allow_redirects=False,
                        ) as response:
                            self.manifest["attempts"].append(
                                {
                                    "status": response.status_code,
                                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                                    "last_modified": response.headers.get("Last-Modified"),
                                }
                            )
                            self.save_manifest()
                            if (
                                response.status_code in {429, 502, 503, 504}
                                and attempt < self.config.retries
                            ):
                                delay = response.headers.get("Retry-After", "")
                                self.sleep(min(30, float(delay)) if delay.isdigit() else 2**attempt)
                                continue
                            if response.status_code != 200:
                                raise SourceError(
                                    f"LISt public download: HTTP {response.status_code}"
                                )
                            digest, size = self.copy_bounded(response.iter_content(65536), partial)
                            break
                    except (requests.Timeout, requests.ConnectionError) as exc:
                        self.manifest["attempts"].append({"transport_error": type(exc).__name__})
                        self.save_manifest()
                        if attempt == self.config.retries:
                            raise SourceError(
                                "LISt transport failure after bounded retries"
                            ) from exc
                        self.sleep(2**attempt)
                else:
                    raise SourceError("LISt download exhausted")
            self.manifest.update(archive_sha256=digest, archive_bytes=size)
            self.save_manifest()
            if digest != self.config.reviewed_archive_sha256:
                raise SourceError(
                    "Archive SHA-256 differs from reviewed snapshot; review the new source before loading"
                )
            downloaded = self.directory / "download.zip"
            partial.replace(downloaded)
            try:
                with ZipFile(downloaded) as zipped:
                    entries = zipped.infolist()
                    if len(entries) != 1 or entries[0].filename != LIST_MEMBER:
                        raise SourceError(
                            "Expected exactly the reviewed GeoPackage member; no path extraction allowed"
                        )
                    member = entries[0]
                    if member.flag_bits & 1 or member.file_size > MAX_GPKG_BYTES:
                        raise SourceError("Encrypted or oversized GeoPackage")
                    self.path = self.directory / LIST_MEMBER
                    total = 0
                    with zipped.open(member) as source, self.path.open("wb") as out:
                        while chunk := source.read(65536):
                            total += len(chunk)
                            if total > MAX_GPKG_BYTES:
                                raise SourceError("Uncompressed GeoPackage exceeds byte limit")
                            out.write(chunk)
            except (BadZipFile, RuntimeError) as exc:
                raise SourceError("Invalid or corrupt source archive") from exc
            return self.inspect()
        finally:
            partial.unlink(missing_ok=True)

    def inspect(self):
        if self.path is None:
            raise SourceError("Acquire an archive before reading features")
        try:
            with sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True) as database:
                database.execute("PRAGMA query_only=ON")
                contents = database.execute(
                    "SELECT table_name,data_type,last_change,srs_id FROM gpkg_contents"
                ).fetchall()
                selected = [
                    row for row in contents if row[0] == self.config.layer and row[1] == "features"
                ]
                if len(selected) != 1 or selected[0][3] != 25833:
                    raise SourceError("Expected reviewed LISt polygon layer in EPSG:25833")
                geometry = database.execute(
                    "SELECT column_name,geometry_type_name,srs_id,z,m FROM gpkg_geometry_columns WHERE table_name=?",
                    (self.config.layer,),
                ).fetchone()
                if geometry != ("geom", "MULTIPOLYGON", 25833, 0, 0):
                    raise SourceError("Unexpected GeoPackage geometry declaration")
                # Layer is allowlisted by Config; SQL identifiers never come from a user URL.
                fields = database.execute(
                    'PRAGMA table_info("Kompensationsmassnahmen_Flaechen")'
                ).fetchall()
                names = {field[1] for field in fields}
                if not ({"ID"} | set(self.config.fields.values())) <= names:
                    raise SourceError("Mapped source attributes are absent from the GeoPackage")
                count = database.execute(
                    'SELECT count(*) FROM "Kompensationsmassnahmen_Flaechen"'
                ).fetchone()[0]
                inventory = []
                for row in contents:
                    item = {
                        "layer": row[0],
                        "last_change": row[2],
                        "srs_id": row[3],
                        "selected": row[0] == self.config.layer,
                    }
                    if row[0] in {
                        "Kompensationsmassnahmen_Linien",
                        "Kompensationsmassnahmen_Flaechen",
                        "Kompensationsmassnahmen_Punkte",
                    }:
                        quoted = '"' + row[0] + '"'  # only the three static allowlisted identifiers
                        item["records"] = database.execute(
                            "SELECT count(*) FROM " + quoted
                        ).fetchone()[0]
                    inventory.append(item)
        except sqlite3.DatabaseError as exc:
            raise SourceError("Invalid GeoPackage SQLite metadata") from exc
        self.manifest.update(
            inventory=inventory,
            selected_count=count,
            source_crs="EPSG:25833",
            schema=[{"name": f[1], "type": f[2]} for f in fields],
        )
        self.save_manifest()
        return self.manifest

    def features(self):
        if self.path is None or "selected_count" not in self.manifest:
            raise SourceError("Inspect the source before reading features")
        received = 0
        for offset in range(0, self.manifest["selected_count"], self.config.page_size):
            frame = gpd.read_file(
                self.path,
                layer=self.config.layer,
                engine="pyogrio",
                rows=slice(offset, offset + self.config.page_size),
                fid_as_index=True,
            )
            if frame.crs is None or CRS.from_user_input(frame.crs).to_epsg() != 25833:
                raise SourceError("Decoded source CRS differs from reviewed metadata")
            if len(frame) != min(self.config.page_size, self.manifest["selected_count"] - offset):
                raise SourceError("GeoPackage batch is incomplete")
            for fid, row in frame.iterrows():
                geometry = row[frame.geometry.name]
                if pd.isna(geometry):
                    geometry = None
                properties = {
                    key: None if pd.isna(value) else value
                    for key, value in row.items()
                    if key != frame.geometry.name
                }
                properties["cid"] = int(
                    fid
                )  # preserve the original storage FID, never use it as site identity
                received += 1
                yield {
                    "type": "Feature",
                    "properties": properties,
                    "geometry": mapping(geometry) if geometry is not None else None,
                }
        if received != self.manifest["selected_count"]:
            raise SourceError("GeoPackage record count changed")
