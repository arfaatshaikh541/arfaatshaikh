"""Register every dataset in data/source-manifest.json and apply its publication decision.

    uv run python scripts/sync_manifest.py              # register + apply
    uv run python scripts/sync_manifest.py --dry-run    # show what would change, change nothing
    uv run python scripts/sync_manifest.py --check      # validate the manifest only (no database)

Run it after every import and after you edit the manifest (for example to record an owner's rights
confirmation). Content whose dataset is not published is hidden from readers, search, the assistant and the graph.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.manifest import load_manifest, validate_manifest  # noqa: E402


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    manifest = load_manifest()
    problems = validate_manifest(manifest)
    if problems:
        print("Manifest problems:\n - " + "\n - ".join(problems))
        raise SystemExit(1)
    print(f"Manifest OK: {len(manifest['datasets'])} datasets")
    if args.check:
        return
    from app.core.config import get_settings
    from app.db.session import Database
    from app.services.datasets import DatasetService
    from app.services.publication_policy import apply_manifest_policy

    db = Database(get_settings())
    async with db.session_factory() as session:
        service = DatasetService(session)
        for entry in manifest["datasets"]:
            await service.register(entry, None)
        await session.flush()
        report = await apply_manifest_policy(session, manifest, dry_run=args.dry_run)
        for row in report:
            print(("SHOW " if row["visible"] else "HIDE ") + row["dataset"], row["targets"])
        if args.dry_run:
            await session.rollback()
            print("dry run: nothing changed")
        else:
            await session.commit()
    await db.dispose()


if __name__ == "__main__":
    asyncio.run(main())
