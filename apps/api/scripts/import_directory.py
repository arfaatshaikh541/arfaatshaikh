"""Governed importer for directory following the platform data contract (docs/data-contracts.md).

    uv run python scripts/import_directory.py --dataset <dataset-id> --file data.json      # import (idempotent)
    uv run python scripts/import_directory.py --dataset <dataset-id> --file data.json --dry-run
    uv run python scripts/import_directory.py --dataset <dataset-id> --rollback <import-id>

Rows are validated one by one and failures are reported. The import is all-or-nothing: one invalid row rejects the whole
file (nothing is written) unless --allow-partial is given. Duplicates and broken fields are never silently repaired.
Importing the same file twice changes nothing. Importing never publishes: a person verifies the dataset and,
if its licence is not clearly open, records the owner's permission (admin API or this repo's manifest).
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _loaders import load_rows  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.services.datasets import DatasetService  # noqa: E402
from app.services.manifest import load_manifest  # noqa: E402

LISTINGS = "directory" == "directory"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--file")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback")
    ap.add_argument("--allow-partial", action="store_true", help="import the valid rows even if some rows fail validation")
    args = ap.parse_args()
    db = Database(get_settings())
    async with db.session_factory() as session:
        service = DatasetService(session)
        entry = next((d for d in load_manifest()["datasets"] if d["id"] == args.dataset), None)
        if entry is None:
            raise SystemExit(f"{args.dataset} is not declared in data/source-manifest.json. Declare its source, licence and provenance first.")
        await service.register(entry, None)
        if args.rollback:
            from uuid import UUID
            imp = await service.rollback_import(UUID(args.rollback), None)  # type: ignore[arg-type]
        else:
            if not args.file:
                raise SystemExit("--file is required")
            rows = load_rows(args.file)
            imp = await (service.import_listings if LISTINGS else service.import_records)(args.dataset, rows, None, strict=not args.allow_partial)
        print(json.dumps({"import": str(imp.id), "status": imp.status, "created": imp.created_count, "updated": imp.updated_count,
                          "unchanged": imp.unchanged_count, "failed": imp.failed_count, "failures": imp.failures[:20]}, indent=1))
        if args.dry_run:
            await session.rollback()
            print("dry run: nothing saved")
        else:
            await session.commit()
    await db.dispose()
    return 1 if imp.status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
