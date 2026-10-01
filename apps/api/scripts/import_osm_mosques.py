"""Import mosque listings for a bounding box from OpenStreetMap (ODbL) via the Overpass API.

    uv run python scripts/import_osm_mosques.py --bbox 53.70,-1.70,53.90,-1.40            # south,west,north,east
    uv run python scripts/import_osm_mosques.py --bbox ... --save mosques.json              # write rows, import nothing
    uv run python scripts/import_osm_mosques.py --from-file overpass.json                   # parse a saved Overpass response

Attribution "(c) OpenStreetMap contributors" is stored on every row. ODbL share-alike applies to derived databases:
read https://www.openstreetmap.org/copyright before publishing. Be considerate to the public Overpass servers
(small boxes, no repeated runs). The dataset directory-mosques stays unpublished until a person verifies and publishes it.
"""
import argparse
import asyncio
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.osm_import import overpass_query, parse_overpass  # noqa: E402

ENDPOINT = "https://overpass-api.de/api/interpreter"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox")
    ap.add_argument("--from-file")
    ap.add_argument("--save")
    ap.add_argument("--dataset", default="directory-mosques")
    args = ap.parse_args()
    if args.from_file:
        payload = json.loads(Path(args.from_file).read_text(encoding="utf-8"))
    elif args.bbox:
        south, west, north, east = (float(x) for x in args.bbox.split(","))
        if (north - south) > 2 or (east - west) > 2:
            raise SystemExit("Choose a smaller area (at most 2 degrees on a side).")
        request = urllib.request.Request(ENDPOINT, data=urllib.parse.urlencode({"data": overpass_query(south, west, north, east)}).encode(), headers={"User-Agent": "WorldOfIslam-importer/1.0"})
        payload = json.loads(urllib.request.urlopen(request, timeout=120).read())
    else:
        raise SystemExit("Give --bbox or --from-file")
    rows, skipped = parse_overpass(payload)
    print(f"{len(rows)} mosques parsed, {len(skipped)} objects skipped (no name or coordinates)")
    if args.save:
        Path(args.save).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"saved to {args.save}; import with scripts/import_directory.py --dataset {args.dataset} --file {args.save}")
        return 0
    from app.core.config import get_settings
    from app.db.session import Database
    from app.services.datasets import DatasetService
    from app.services.manifest import load_manifest
    db = Database(get_settings())
    async with db.session_factory() as session:
        service = DatasetService(session)
        entry = next(d for d in load_manifest()["datasets"] if d["id"] == args.dataset)
        await service.register(entry, None)
        imp = await service.import_listings(args.dataset, rows, None)
        await session.commit()
        print({"created": imp.created_count, "updated": imp.updated_count, "unchanged": imp.unchanged_count, "failed": imp.failed_count})
    await db.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
