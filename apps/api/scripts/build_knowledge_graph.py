"""Build/refresh the knowledge graph from published data (idempotent).   uv run python scripts/build_knowledge_graph.py"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.services.knowledge_graph_builder import build_core_graph  # noqa: E402


async def main() -> None:
    db = Database(get_settings())
    async with db.session_factory() as session:
        print(await build_core_graph(session))
        await session.commit()
    await db.dispose()


if __name__ == "__main__":
    asyncio.run(main())
