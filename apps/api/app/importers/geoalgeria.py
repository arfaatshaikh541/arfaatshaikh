"""Algerian mosques from the npm package @geoalgeria/mosquees (composite of Wikidata CC0 and OpenStreetMap ODbL).

Nothing is added or corrected: names, coordinates and the denomination come from the package; a record without a name is
skipped (not given one); a denomination is kept only when the package took it from OpenStreetMap, with that source stated;
the source's own record identifiers (GeoAlgeria id, Wikidata Q-number, OSM element) are preserved on every listing.
"""
from __future__ import annotations

import json

from app.importers.acquire import npm_package, sha256
from app.importers.base import AdapterResult, FetchResult, SourceAdapter

PACKAGE, VERSION = "@geoalgeria/mosquees", "2.0.4"
RETRIEVED = "2026-06-25"  # dataset-metadata.json: the date the composite was built from Wikidata and OpenStreetMap
OSM_LICENCE = "ODbL 1.0 (© OpenStreetMap contributors)"
WIKIDATA_LICENCE = "CC0-1.0 (Wikidata)"


def build_rows(records: list[dict]) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    skipped = {"no_name": 0}
    for r in records:
        name = (r.get("name") or r.get("name_ar") or r.get("name_fr") or "").strip()
        if len(name) < 2:
            skipped["no_name"] += 1
            continue
        refs = r.get("refs") or {}
        from_osm = "osm" in (r.get("source") or "")
        if refs.get("osm"):
            kind, ident = refs["osm"].split("/", 1)
            url = f"https://www.openstreetmap.org/{kind}/{ident}"
        elif refs.get("wikidata"):
            url = f"https://www.wikidata.org/wiki/{refs['wikidata']}"
        else:
            url = None
        attributes = {k: r[k] for k in ("commune_code", "wilaya_code", "geo_precision", "geo_method", "name_fr") if r.get(k)}
        attributes["geoalgeria_id"] = r["id"]
        if refs.get("wikidata"):
            attributes["wikidata"] = refs["wikidata"]
        if refs.get("osm"):
            attributes["osm"] = refs["osm"]
        if r.get("denomination") and from_osm:
            attributes["denomination"] = r["denomination"]
            attributes["denomination_source"] = "OpenStreetMap denomination tag (via GeoAlgeria)"
        rows.append({
            "external_key": f"geoalgeria:{r['id']}", "listing_type": "mosque", "name": name, "arabic_name": r.get("name_ar") or None,
            "city": r.get("commune") or None, "country": "DZ", "latitude": r["lat"], "longitude": r["lng"],
            "source": f"GeoAlgeria @geoalgeria/mosquees {VERSION} (composite of {r.get('source', 'wikidata')})", "source_url": url,
            "license": OSM_LICENCE if from_osm else WIKIDATA_LICENCE,
            "provenance": (f"Compiled by GeoAlgeria ({PACKAGE} {VERSION}, built {RETRIEVED}) from {r.get('source')}; coordinate precision {r.get('geo_precision')}. "
                           "The commune is derived by nearest-centroid join and is best-effort, not from the source. Not an official registry."),
            "source_updated_at": RETRIEVED, "attributes": attributes,
        })
    return rows, skipped


class GeoAlgeriaMosques(SourceAdapter):
    id = "geoalgeria-mosquees"
    dataset_key = "directory-mosques"
    kind = "listings"
    title = "Mosques of Algeria (GeoAlgeria composite of Wikidata and OpenStreetMap)"
    probe_urls = ("https://registry.npmjs.org/@geoalgeria%2fmosquees/2.0.4",)
    licence_summary = "ODbL 1.0 (© OpenStreetMap contributors) for OSM-derived records; CC0-1.0 for Wikidata records"
    country = "DZ"

    def fetch(self, params: dict) -> FetchResult:
        package, files, tarball_sha = npm_package(PACKAGE, VERSION)
        if package.get("license") != "MIT AND ODbL-1.0":
            raise SystemExit(f"licence changed upstream ({package.get('license')!r}); refusing to import until it is re-verified")
        data = files["data/mosquees.json"]
        return FetchResult(version=f"{PACKAGE}@{VERSION}", checksum=tarball_sha, payload=json.loads(data), source_url=f"https://www.npmjs.com/package/{PACKAGE}/v/{VERSION}",
                           notes={"records_sha256": sha256(data), "dataset_metadata": json.loads(files["dataset-metadata.json"]).get("dateModified")})

    def build(self, fetched: FetchResult, params: dict) -> AdapterResult:
        rows, skipped = build_rows(fetched.payload)
        return AdapterResult(rows=rows, skipped=skipped, stats={"source_records": len(fetched.payload), "rows": len(rows), "country": self.country})
