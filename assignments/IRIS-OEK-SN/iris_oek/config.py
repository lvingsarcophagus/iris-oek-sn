"""Explicit, reviewed mappings; no attribute-name heuristics."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from iris_oek import ENDPOINT, LAYER
from iris_oek.sources import PROFILES


@dataclass(frozen=True)
class Config:
    source_kind: str = "wfs"
    endpoint: str = ENDPOINT
    layer: str = LAYER
    page_size: int = 100
    max_pages: int = 1000
    timeout_seconds: float = 30
    request_interval_seconds: float = 1
    retries: int = 2
    max_response_bytes: int = 20_000_000
    reviewed_schema_sha256: str | None = None
    id_field: str | None = None  # None means the GeoJSON feature id, never a row number.
    fields: dict = field(default_factory=dict)
    status_values: dict = field(default_factory=dict)
    state_values: list = field(default_factory=lambda: ["SN", "14"])
    area_unit: str | None = None
    credit_unit: str | None = None
    reviewed_archive_sha256: str | None = None

    def __post_init__(self):
        profile = PROFILES.get(self.source_kind)
        if profile is None or (self.endpoint, self.layer) != (profile.endpoint, profile.layer):
            raise ValueError(
                "Endpoint and layer must match an explicitly allowlisted source profile"
            )
        if self.source_kind == "list_geopackage":
            if self.id_field != "ID":
                raise ValueError("The reviewed LISt source identifier is ID")
            if not re.fullmatch(r"[0-9a-f]{64}", self.reviewed_archive_sha256 or ""):
                raise ValueError("LISt ingestion requires a reviewed archive SHA-256")
        if not (1 <= self.page_size <= 1000 and 1 <= self.max_pages <= 10_000):
            raise ValueError("Invalid page limits")
        if not (0 < self.timeout_seconds <= 120 and 0 <= self.retries <= 3):
            raise ValueError("Invalid timeout/retry limits")
        if not (0 <= self.request_interval_seconds <= 60):
            raise ValueError("Invalid request interval")
        if not (1024 <= self.max_response_bytes <= 100_000_000):
            raise ValueError("Invalid response size limit")
        allowed = {"municipality", "cadastre", "status", "area", "credits", "state"}
        if set(self.fields) - allowed or any(not isinstance(v, str) for v in self.fields.values()):
            raise ValueError("Unknown or invalid field mapping")
        if "area" in self.fields and self.area_unit not in {"m2", "ha"}:
            raise ValueError("A mapped area requires a verified m2 or ha unit")
        if "credits" in self.fields and not self.credit_unit:
            raise ValueError("A mapped credit requires a verified unit")

    @classmethod
    def read(cls, path: Path):
        return cls(**json.loads(path.read_text(encoding="utf-8")))

    @property
    def profile(self):
        return PROFILES[self.source_kind]
