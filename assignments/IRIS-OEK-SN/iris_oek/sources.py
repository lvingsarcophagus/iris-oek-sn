"""Allowlisted sources and their distinct, explicitly documented domains."""

from dataclasses import dataclass

from iris_oek import ENDPOINT, LAYER

LIST_ENDPOINT = "https://www.list.smwa.sachsen.de/inspire/download/DE-SN-SBV_INSPIRE_Downloadservice_Kompensationsflaechen.zip"
LIST_LAYER = "Kompensationsmassnahmen_Flaechen"
LIST_MEMBER = "DE-SN-SBV_INSPIRE_Downloadservice_Kompensationsflaechen.gpkg"
LIST_NAMESPACE = "urn:iris:source:list-sn-kiss-koka-nat-public"
LIST_CATALOG = "https://data.gov.de/suche/daten/kompensationsmassnahmen-informationssystem-kompensationsflachenkataster-sachsen87dcd"
LIST_ATTRIBUTION = "Quelle: Kompensationsmaßnahmen-Informationssystem Freistaat Sachsen"
LIST_LICENSE = "https://www.govdata.de/dl-de/by-2-0"


@dataclass(frozen=True)
class SourceProfile:
    endpoint: str
    layer: str
    domain: str
    license_url: str | None = None
    attribution: str | None = None


PROFILES = {
    "wfs": SourceProfile(ENDPOINT, LAYER, "compensation_parcels"),
    "list_geopackage": SourceProfile(
        LIST_ENDPOINT, LIST_LAYER, "compensation_measures", LIST_LICENSE, LIST_ATTRIBUTION
    ),
}
