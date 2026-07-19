import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.exceptions import ValidationAppError
from app.dependencies import TenantContext, require_permission
from app.modules.csv_import import repositories as csv_import_repo
from app.modules.csv_import import services
from app.modules.csv_import.models import MAPPABLE_FIELDS
from app.modules.csv_import.schemas import (
    CsvImportErrorListResponse,
    CsvImportErrorResponse,
    CsvImportListResponse,
    CsvImportPreviewResponse,
    CsvImportResponse,
    StartCsvImportRequest,
)

router = APIRouter(prefix="/imports", tags=["csv-import"])

# 10 MB - generous for a business-list CSV, small enough that a request
# body is never read unbounded into memory before this check runs.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post("", response_model=CsvImportPreviewResponse)
async def upload_csv(
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(require_permission("campaigns.create")),
    db: AsyncSession = Depends(get_db),
):
    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise ValidationAppError(f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")
    csv_import = await services.preview_csv(
        db,
        tenant_id=ctx.tenant_id,
        requested_by_user_id=ctx.user_id,
        filename=file.filename or "upload.csv",
        file_bytes=file_bytes,
    )
    return CsvImportPreviewResponse.from_model(csv_import, mappable_fields=list(MAPPABLE_FIELDS))


@router.post("/{csv_import_id}/start", response_model=CsvImportResponse)
async def start_csv_import(
    csv_import_id: uuid.UUID,
    request: StartCsvImportRequest,
    ctx: TenantContext = Depends(require_permission("campaigns.create")),
    db: AsyncSession = Depends(get_db),
):
    csv_import = await csv_import_repo.get_csv_import_or_raise(db, csv_import_id)
    updated = await services.start_import(db, csv_import, request=request)
    return CsvImportResponse.from_model(updated)


@router.get("", response_model=CsvImportListResponse)
async def list_csv_imports(
    ctx: TenantContext = Depends(require_permission("campaigns.view")),
    db: AsyncSession = Depends(get_db),
):
    imports = await csv_import_repo.list_csv_imports_for_tenant(db, ctx.tenant_id)
    return CsvImportListResponse(imports=[CsvImportResponse.from_model(i) for i in imports])


@router.get("/{csv_import_id}", response_model=CsvImportResponse)
async def get_csv_import(
    csv_import_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("campaigns.view")),
    db: AsyncSession = Depends(get_db),
):
    csv_import = await csv_import_repo.get_csv_import_or_raise(db, csv_import_id)
    return CsvImportResponse.from_model(csv_import)


@router.get("/{csv_import_id}/errors", response_model=CsvImportErrorListResponse)
async def get_csv_import_errors(
    csv_import_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("campaigns.view")),
    db: AsyncSession = Depends(get_db),
):
    await csv_import_repo.get_csv_import_or_raise(db, csv_import_id)
    errors = await csv_import_repo.list_errors_for_csv_import(db, csv_import_id)
    return CsvImportErrorListResponse(
        errors=[CsvImportErrorResponse(row_number=e.row_number, message=e.message) for e in errors]
    )
