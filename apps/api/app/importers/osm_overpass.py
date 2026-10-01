"""Mosques for one area from OpenStreetMap through the Overpass API (ODbL 1.0, © OpenStreetMap contributors).

This is the scalable route to other countries: the administrator supplies a bounding box and the ISO country code. It was
NOT run against the live API from the build environment (Overpass is unreachable there), so it is exercised by tests on the
Overpass JSON shape only. Unnamed objects are skipped; nothing else is inferred.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

from app.importers.acquire import UA, sha256
from app.importers.base import AdapterResult, FetchResult, SourceAdapter
from app.services.osm_import import overpass_query, parse_overpass

ENDPOINT = "https://overpass-api.de/api/interpreter"


def parse_bbox(value: str) -> tuple[float, float, float, float]:
    south, west, north, east = (float(x) for x in value.split(","))
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError("bbox must be south,west,north,east in degrees")
    if (north - south) > 2 or (east - west) > 2:
        raise ValueError("choose a smaller area (at most 2 degrees on a side)")
    return south, west, north, east


class OsmOverpassMosques(SourceAdapter):
    id = "osm-overpass-mosques"
    dataset_key = "directory-mosques"
    kind = "listings"
    title = "Mosques in a bounding box from OpenStreetMap (Overpass API)"
    probe_urls = ("https://overpass-api.de/api/status",)
    licence_summary = "ODbL 1.0 (© OpenStreetMap contributors); share-alike applies to a derived database"
    params_help = {"bbox": "south,west,north,east (at most 2 degrees on a side)", "country": "ISO 3166-1 alpha-2 code of the area"}

    def fetch(self, params: dict) -> FetchResult:
        box = parse_bbox(params["bbox"])
        request = urllib.request.Request(ENDPOINT, data=urllib.parse.urlencode({"data": overpass_query(*box)}).encode(), headers=UA)
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read()
        return FetchResult(version=f"overpass bbox {params['bbox']}", checksum=sha256(raw), payload=json.loads(raw), source_url=ENDPOINT)

    def build(self, fetched: FetchResult, params: dict) -> AdapterResult:
        country = (params.get("country") or "").upper()
        if len(country) != 2:
            raise ValueError("country (ISO alpha-2) is required so coverage is stated honestly")
        rows, skipped = parse_overpass(fetched.payload)
        for row in rows:
            row["country"] = row.get("country") or country
        return AdapterResult(rows=rows, skipped={"no_name_or_coordinates": len(skipped)}, stats={"rows": len(rows), "country": country})
