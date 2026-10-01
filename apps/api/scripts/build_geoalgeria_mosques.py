"""Build directory listings for Algeria's mosques from the npm package @geoalgeria/mosquees (exact version, integrity-checked).

    uv run python scripts/build_geoalgeria_mosques.py --out /tmp/dz-mosques.json
    uv run python scripts/import_directory.py --dataset directory-mosques --file /tmp/dz-mosques.json   # chunked by this script

Source: GeoAlgeria composite of Wikidata (CC0-1.0) and OpenStreetMap (ODbL 1.0, (c) OpenStreetMap contributors).
Nothing is added or corrected here: coordinates, names and the denomination come from the package; a record without a
name is skipped (not given a made-up one); a denomination is kept only when the package took it from OpenStreetMap.
ODbL share-alike applies to a derived database: keep the attribution that every listing carries.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _acquire import npm_package  # noqa: E402

PACKAGE, VERSION = "@geoalgeria/mosquees", "2.0.4"
RETRIEVED = "2026-06-25"  # dataset-metadata.json: the date the composite was built from Wikidata and OpenStreetMap
OSM_LICENCE = "ODbL 1.0 (© OpenStreetMap contributors)"
WIKIDATA_LICENCE = "CC0-1.0 (Wikidata)"


def build(records: list[dict]) -> tuple[list[dict], dict]:
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--chunk", type=int, default=5000)
    args = ap.parse_args()
    package, files, tarball_sha = npm_package(PACKAGE, VERSION)
    assert package["license"] == "MIT AND ODbL-1.0", package["license"]
    records = json.loads(files["data/mosquees.json"])
    rows, skipped = build(records)
    out = Path(args.out)
    out.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    chunks = [rows[i:i + args.chunk] for i in range(0, len(rows), args.chunk)]
    for index, chunk in enumerate(chunks):
        out.with_suffix(f".{index}.json").write_text(json.dumps(chunk, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"package": f"{PACKAGE}@{VERSION}", "tarball_sha256": tarball_sha,
                      "source_records": len(records), "rows": len(rows), "skipped": skipped, "chunks": len(chunks)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
