"""Run every source-sensitive data validation against the configured database. Exit code 1 on any violation.

    uv run python scripts/validate_data.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.services.data_validation import validate_database  # noqa: E402
from app.services.manifest import load_manifest  # noqa: E402


async def main() -> int:
    db = Database(get_settings())
    async with db.session_factory() as session:
        results = await validate_database(session, load_manifest())
    await db.dispose()
    failed = 0
    for name, problems in results.items():
        print(("PASS " if not problems else "FAIL ") + name)
        for problem in problems[:20]:
            print("   - " + problem)
        failed += bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
