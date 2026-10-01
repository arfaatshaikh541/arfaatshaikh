"""Turn OpenStreetMap (Overpass JSON) mosque elements into directory-contract rows.

Data licence: ODbL 1.0, attribution "(c) OpenStreetMap contributors". Every produced row carries that licence and the
OSM element id as its provenance and external key, so a re-import updates in place and an administrator can trace each
listing to its OSM object. Nothing is invented: fields OSM does not have stay empty, and unnamed objects are skipped.
"""
from __future__ import annotations

OSM_LICENCE = "ODbL 1.0 - (c) OpenStreetMap contributors"
OSM_SOURCE = "OpenStreetMap"


def overpass_query(south: float, west: float, north: float, east: float) -> str:
    box = f"{south},{west},{north},{east}"
    return f'[out:json][timeout:60];(node["amenity"="place_of_worship"]["religion"="muslim"]({box});way["amenity"="place_of_worship"]["religion"="muslim"]({box});relation["amenity"="place_of_worship"]["religion"="muslim"]({box}););out center tags;'


def parse_overpass(payload: dict) -> tuple[list[dict], list[dict]]:
    """Returns (listing rows, skipped objects with the reason)."""
    rows: list[dict] = []
    skipped: list[dict] = []
    for element in payload.get("elements", []):
        kind, osm_id, tags = element.get("type"), element.get("id"), element.get("tags") or {}
        ref = f"{kind}/{osm_id}"
        name = (tags.get("name") or tags.get("name:en") or "").strip()
        if not name or len(name) < 2:
            skipped.append({"id": ref, "reason": "no name tag"})
            continue
        lat = element.get("lat", (element.get("center") or {}).get("lat"))
        lon = element.get("lon", (element.get("center") or {}).get("lon"))
        if lat is None or lon is None:
            skipped.append({"id": ref, "reason": "no coordinates"})
            continue
        street = " ".join(x for x in (tags.get("addr:housenumber"), tags.get("addr:street")) if x)
        address = ", ".join(x for x in (street, tags.get("addr:postcode")) if x) or None
        website = tags.get("website") or tags.get("contact:website")
        if website and not website.startswith(("http://", "https://")):
            website = "https://" + website
        email = tags.get("email") or tags.get("contact:email")
        rows.append({
            "external_key": ref, "listing_type": "mosque", "name": name[:300], "arabic_name": (tags.get("name:ar") or None),
            "description": None, "category": tags.get("denomination") or tags.get("building") or None, "tags": [t for t in ("wheelchair" if tags.get("wheelchair") == "yes" else None,) if t],
            "address": address, "city": tags.get("addr:city"), "region": tags.get("addr:state"), "country": (tags.get("addr:country") or None),
            "latitude": float(lat), "longitude": float(lon), "phone": tags.get("phone") or tags.get("contact:phone"),
            "email": email if email and "@" in email else None, "website": website,
            "source": OSM_SOURCE, "source_url": f"https://www.openstreetmap.org/{ref}", "license": OSM_LICENCE,
            "provenance": f"OpenStreetMap {ref}, retrieved through the Overpass API", "source_updated_at": None,
        })
    return rows, skipped
