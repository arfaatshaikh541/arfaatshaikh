import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_client import enqueue_csv_import
from app.core.exceptions import ConflictError, ValidationAppError
from app.core.storage import upload_bytes
from app.modules.csv_import import repositories as csv_import_repo
from app.modules.csv_import.models import MAPPABLE_FIELDS, CsvImport
from app.modules.csv_import.parsing import MAX_PREVIEW_ROWS, CsvParseError, read_headers_and_rows
from app.modules.csv_import.schemas import StartCsvImportRequest
from app.modules.usage.services import reserve_credits


async def preview_csv(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    requested_by_user_id: uuid.UUID | None,
    filename: str,
    file_bytes: bytes,
) -> CsvImport:
    try:
        headers, rows = read_headers_and_rows(file_bytes)
    except CsvParseError as exc:
        raise ValidationAppError(str(exc)) from exc
    if not rows:
        raise ValidationAppError("File has a header row but no data rows.")

    object_key = f"tenants/{tenant_id}/csv_imports/{uuid.uuid4()}/{filename}"
    upload_bytes(key=object_key, data=file_bytes, content_type="text/csv")

    return await csv_import_repo.create_csv_import(
        session,
        tenant_id=tenant_id,
        requested_by_user_id=requested_by_user_id,
        object_key=object_key,
        original_filename=filename,
        detected_headers=headers,
        sample_rows=rows[:MAX_PREVIEW_ROWS],
        row_count=len(rows),
    )


async def start_import(
    session: AsyncSession, csv_import: CsvImport, *, request: StartCsvImportRequest
) -> CsvImport:
    if csv_import.status != "mapping_required":
        raise ConflictError(f"Import is already {csv_import.status}; cannot start it again.")

    unknown_fields = set(request.column_mapping) - set(MAPPABLE_FIELDS)
    if unknown_fields:
        raise ValidationAppError(f"Unknown mapping field(s): {', '.join(sorted(unknown_fields))}")
    if "name" not in request.column_mapping:
        raise ValidationAppError("column_mapping must map 'name' to a CSV column.")
    if not set(request.column_mapping.values()) <= set(csv_import.detected_headers):
        raise ValidationAppError("column_mapping references a column not present in the file.")

    reservation = await reserve_credits(
        session,
        tenant_id=csv_import.tenant_id,
        amount=float(csv_import.row_count),
        reference=f"csv_import:{csv_import.id}",
    )
    await csv_import_repo.mark_queued(
        session, csv_import, column_mapping=request.column_mapping, reservation_id=reservation.id
    )
    await session.commit()
    enqueue_csv_import(str(csv_import.id))
    return csv_import
