import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.modules.csv_import.models import CsvImport, CsvImportError


async def create_csv_import(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    requested_by_user_id: uuid.UUID | None,
    object_key: str,
    original_filename: str,
    detected_headers: list[str],
    sample_rows: list[dict],
    row_count: int,
) -> CsvImport:
    csv_import = CsvImport(
        tenant_id=tenant_id,
        requested_by_user_id=requested_by_user_id,
        status="mapping_required",
        object_key=object_key,
        original_filename=original_filename,
        detected_headers=detected_headers,
        sample_rows=sample_rows,
        row_count=row_count,
    )
    session.add(csv_import)
    await session.flush()
    return csv_import


async def get_csv_import(session: AsyncSession, csv_import_id: uuid.UUID) -> CsvImport | None:
    stmt = select(CsvImport).where(CsvImport.id == csv_import_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_csv_import_or_raise(session: AsyncSession, csv_import_id: uuid.UUID) -> CsvImport:
    csv_import = await get_csv_import(session, csv_import_id)
    if csv_import is None:
        raise ResourceNotFoundError("CSV import not found.")
    return csv_import


async def list_csv_imports_for_tenant(
    session: AsyncSession, tenant_id: uuid.UUID, *, limit: int = 100
) -> list[CsvImport]:
    stmt = (
        select(CsvImport)
        .where(CsvImport.tenant_id == tenant_id)
        .order_by(CsvImport.created_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def mark_queued(
    session: AsyncSession, csv_import: CsvImport, *, column_mapping: dict, reservation_id: uuid.UUID
) -> None:
    csv_import.status = "queued"
    csv_import.column_mapping = column_mapping
    csv_import.reservation_id = reservation_id
    await session.flush()


async def mark_processing(session: AsyncSession, csv_import: CsvImport, *, started_at: datetime) -> None:
    csv_import.status = "processing"
    csv_import.started_at = started_at
    await session.flush()


async def mark_completed(
    session: AsyncSession,
    csv_import: CsvImport,
    *,
    completed_at: datetime,
    imported_count: int,
    error_count: int,
) -> None:
    csv_import.status = "completed"
    csv_import.completed_at = completed_at
    csv_import.imported_count = imported_count
    csv_import.error_count = error_count
    await session.flush()


async def mark_failed(
    session: AsyncSession, csv_import: CsvImport, *, completed_at: datetime, message: str
) -> None:
    csv_import.status = "failed"
    csv_import.completed_at = completed_at
    csv_import.error_message = message[:2000]
    await session.flush()


async def create_import_error(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    csv_import_id: uuid.UUID,
    row_number: int,
    message: str,
) -> CsvImportError:
    entry = CsvImportError(
        tenant_id=tenant_id,
        csv_import_id=csv_import_id,
        row_number=row_number,
        message=message[:2000],
    )
    session.add(entry)
    return entry


async def list_errors_for_csv_import(
    session: AsyncSession, csv_import_id: uuid.UUID
) -> list[CsvImportError]:
    stmt = (
        select(CsvImportError)
        .where(CsvImportError.csv_import_id == csv_import_id)
        .order_by(CsvImportError.row_number)
    )
    return list((await session.execute(stmt)).scalars().all())
