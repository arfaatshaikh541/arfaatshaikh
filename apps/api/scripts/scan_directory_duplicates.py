"""Link probable duplicate directory listings (same normalised name and city, within 200 m or without coordinates).

    uv run python scripts/scan_directory_duplicates.py

The later listing is marked as a duplicate of the earlier one and drops out of public results; nothing is deleted, and an
administrator can review every link. The admin API exposes the same scan.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import import_real_evidence as base  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.services.directory import DirectoryService  # noqa: E402


async def main() -> None:
    db = Database(get_settings())
    async with db.session_factory() as session:
        actor = await base.get_or_create_operator(session)
        linked = await DirectoryService(session).scan_duplicates(actor)
        await session.commit()
        print(f"{linked} listings linked as duplicates")
    await db.dispose()


if __name__ == "__main__":
    asyncio.run(main())
