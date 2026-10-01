"""Run a registered source adapter: preview by default, --apply to import (all-or-nothing). Safe to re-run.

    uv run python scripts/run_importer.py --list
    uv run python scripts/run_importer.py geoalgeria-mosquees                      # fetch, validate, show what would change
    uv run python scripts/run_importer.py geoalgeria-mosquees --apply
    uv run python scripts/run_importer.py osm-overpass-mosques --param bbox=36.7,3.0,36.8,3.1 --param country=DZ
    uv run python scripts/run_importer.py hadith-api-grades --apply                  # imports HIDDEN: rights are not established

Importing never publishes and never verifies; use scripts/dataset_action.py (or Data & trust) for that.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import import_real_evidence as base  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.importers import ADAPTERS, get_adapter  # noqa: E402
from app.importers.runner import run_adapter  # noqa: E402
from app.services.datasets import DatasetService  # noqa: E402
from app.services.manifest import load_manifest  # noqa: E402


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("adapter", nargs="?")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--probe", action="store_true", help="only check whether the source is reachable from here")
    ap.add_argument("--param", action="append", default=[], help="key=value for adapters that take parameters")
    args = ap.parse_args()
    if args.list or not args.adapter:
        print(json.dumps([a.describe() for a in ADAPTERS.values()], indent=1))
        return 0
    adapter = get_adapter(args.adapter)
    if args.probe:
        print(json.dumps(adapter.probe(), indent=1))
        return 0
    params = dict(p.split("=", 1) for p in args.param)
    db = Database(get_settings())
    async with db.session_factory() as session:
        entry = next(d for d in load_manifest()["datasets"] if d["id"] == adapter.dataset_key)
        await DatasetService(session).register(entry, None)
        actor = await base.get_or_create_operator(session)
        result = await run_adapter(session, adapter, params, apply=args.apply, actor=actor)
        if args.apply:
            await session.commit()
        print(json.dumps(result, indent=1, default=str)[:6000])
    await db.dispose()
    return 1 if args.apply and not result["applied"] and result.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
