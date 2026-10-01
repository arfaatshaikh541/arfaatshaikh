"""Command-line twin of the admin "Data & trust" actions, for operators without the web admin.

    uv run python scripts/dataset_action.py --dataset directory-mosques --action mark_verified --note "Checked licence text, coordinates, duplicates"
    uv run python scripts/dataset_action.py --dataset directory-mosques --action publish
    uv run python scripts/dataset_action.py --dataset hadith-grading --action publish --confirmed-by "Name" --basis "Written permission from ..."
    uv run python scripts/dataset_action.py --dataset hadith-grading --action unpublish

Publishing follows the same gate as the admin API (licence status, validation status, recorded rights confirmation) and is audited.
"""
import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import import_real_evidence as base  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.errors import ApplicationError  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.services.datasets import ACTIONS, DatasetService  # noqa: E402


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--action", required=True, choices=sorted(ACTIONS))
    ap.add_argument("--note")
    ap.add_argument("--confirmed-by")
    ap.add_argument("--basis")
    args = ap.parse_args()
    confirmation = {"confirmed_by": args.confirmed_by, "confirmed_on": date.today().isoformat(), "basis": args.basis} if args.confirmed_by or args.basis else None
    db = Database(get_settings())
    async with db.session_factory() as session:
        actor = await base.get_or_create_operator(session)
        try:
            dataset = await DatasetService(session).apply_action(args.dataset, args.action, actor, note=args.note, rights_confirmation=confirmation)
        except ApplicationError as exc:
            print(f"REFUSED: {exc.message} {exc.details if getattr(exc, 'details', None) else ''}")
            return 1
        await session.commit()
        print(f"{dataset.dataset_key}: publication={dataset.publication_status} validation={dataset.validation_status} licence={dataset.license_status} enabled={dataset.enabled}")
    await db.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
