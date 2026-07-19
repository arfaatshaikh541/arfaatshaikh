import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.modules.exports.models import Export, ExportError


async def create_export(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    requested_by_user_id: uuid.UUID | None,
    format: str,
    selection: dict,
) -> Export:
    export = Export(
        tenant_id=tenant_id,
        requested_by_user_id=requested_by_user_id,
        format=format,
        status="pending",
        selection=selection,
    )
    session.add(export)
    await session.flush()
    return export


async def get_export(session: AsyncSession, export_id: uuid.UUID) -> Export | None:
    stmt = select(Export).where(Export.id == export_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_export_or_raise(session: AsyncSession, export_id: uuid.UUID) -> Export:
    export = await get_export(session, export_id)
    if export is None:
        raise ResourceNotFoundError("Export not found.")
    return export


async def list_exports_for_tenant(
    session: AsyncSession, tenant_id: uuid.UUID, *, limit: int = 100
) -> list[Export]:
    stmt = (
        select(Export)
        .where(Export.tenant_id == tenant_id)
        .order_by(Export.created_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def mark_processing(session: AsyncSession, export: Export, *, started_at: datetime) -> None:
    export.status = "processing"
    export.started_at = started_at
    await session.flush()


async def mark_completed(
    session: AsyncSession,
    export: Export,
    *,
    completed_at: datetime,
    object_key: str,
    file_size_bytes: int,
    row_count: int,
    error_count: int,
    expires_at: datetime | None,
) -> None:
    export.status = "completed"
    export.completed_at = completed_at
    export.object_key = object_key
    export.file_size_bytes = file_size_bytes
    export.row_count = row_count
    export.error_count = error_count
    export.expires_at = expires_at
    await session.flush()


async def mark_failed(
    session: AsyncSession, export: Export, *, completed_at: datetime, message: str
) -> None:
    export.status = "failed"
    export.completed_at = completed_at
    export.error_message = message[:2000]
    await session.flush()


async def list_expired_uncleaned_exports(session: AsyncSession, *, now: datetime) -> list[Export]:
    """Cross-tenant query used only by the maintenance sweep task
    (`worker.export_cleanup_tasks`), which runs under `set_platform_bypass`
    - the same shape as `usage.repositories.list_expired_pending_
    reservations` - since the whole point is finding stale exports across
    every tenant, not one at a time."""
    stmt = select(Export).where(
        Export.status == "completed",
        Export.expires_at.is_not(None),
        Export.expires_at < now,
        Export.storage_deleted_at.is_(None),
        Export.object_key.is_not(None),
    )
    return list((await session.execute(stmt)).scalars().all())


async def mark_storage_deleted(
    session: AsyncSession, export: Export, *, deleted_at: datetime
) -> None:
    export.storage_deleted_at = deleted_at
    await session.flush()


async def create_export_error(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    export_id: uuid.UUID,
    lead_id: uuid.UUID | None,
    message: str,
) -> ExportError:
    entry = ExportError(
        tenant_id=tenant_id, export_id=export_id, lead_id=lead_id, message=message[:2000]
    )
    session.add(entry)
    return entry


async def list_errors_for_export(session: AsyncSession, export_id: uuid.UUID) -> list[ExportError]:
    stmt = (
        select(ExportError)
        .where(ExportError.export_id == export_id)
        .order_by(ExportError.created_at)
    )
    return list((await session.execute(stmt)).scalars().all())
