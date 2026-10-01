from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.importers.base import SourceAdapter
from app.models.identity import User
from app.services.datasets import DatasetService, MAX_ERRORS_REPORTED


async def run_adapter(session: AsyncSession, adapter: SourceAdapter, params: dict, *, apply: bool, actor: User | None) -> dict:
    """Fetch, build, preview and (only if `apply`) import all-or-nothing. A re-run of an unchanged source changes nothing.

    The caller commits. Fetching and mapping run in a worker thread so they never block the event loop.
    """
    service = DatasetService(session)
    await service.by_key(adapter.dataset_key)  # the dataset must already be declared in the manifest and registered
    fetched = await asyncio.to_thread(adapter.fetch, params)
    built = await asyncio.to_thread(adapter.build, fetched, params)
    if len(built.rows) > adapter.max_rows:
        raise ValueError(f"{len(built.rows)} rows exceeds this adapter's limit of {adapter.max_rows}")
    preview = await (service.preview_listings if adapter.kind == "listings" else service.preview_records)(adapter.dataset_key, built.rows)
    result = {"adapter": adapter.id, "dataset": adapter.dataset_key, "source_version": fetched.version, "source_checksum": fetched.checksum, "retrieved_at": fetched.retrieved_at.isoformat(),
              "skipped": built.skipped, "stats": built.stats, "preview": {**preview, "failures": preview["failures"][:MAX_ERRORS_REPORTED]}, "applied": False}
    if not apply:
        return result
    source = {"adapter_id": adapter.id, "source_version": fetched.version, "source_retrieved_at": fetched.retrieved_at, "source_checksum": fetched.checksum}
    importer = service.import_listings if adapter.kind == "listings" else service.import_records
    imp = await importer(adapter.dataset_key, built.rows, actor, strict=True, max_records=adapter.max_rows, source=source)
    result.update(applied=imp.status == "applied", import_id=str(imp.id), status=imp.status, created=imp.created_count, updated=imp.updated_count, unchanged=imp.unchanged_count, failed=imp.failed_count)
    return result


def now() -> datetime:
    return datetime.now(UTC)
