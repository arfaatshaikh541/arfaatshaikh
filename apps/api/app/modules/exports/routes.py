import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.dependencies import TenantContext, require_permission
from app.modules.exports import repositories as exports_repo
from app.modules.exports import services
from app.modules.exports.schemas import (
    CreateExportRequest,
    ExportDownloadResponse,
    ExportErrorListResponse,
    ExportErrorResponse,
    ExportListResponse,
    ExportResponse,
)

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post("", response_model=ExportResponse)
async def create_export(
    request: CreateExportRequest,
    ctx: TenantContext = Depends(require_permission("leads.export")),
    db: AsyncSession = Depends(get_db),
):
    export = await services.request_export(
        db,
        tenant_id=ctx.tenant_id,
        requested_by_user_id=ctx.user_id,
        request=request,
    )
    return ExportResponse.from_model(export)


@router.get("", response_model=ExportListResponse)
async def list_exports(
    ctx: TenantContext = Depends(require_permission("exports.view")),
    db: AsyncSession = Depends(get_db),
):
    exports = await exports_repo.list_exports_for_tenant(db, ctx.tenant_id)
    return ExportListResponse(exports=[ExportResponse.from_model(e) for e in exports])


@router.get("/{export_id}", response_model=ExportResponse)
async def get_export(
    export_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("exports.view")),
    db: AsyncSession = Depends(get_db),
):
    export = await exports_repo.get_export_or_raise(db, export_id)
    return ExportResponse.from_model(export)


@router.get("/{export_id}/errors", response_model=ExportErrorListResponse)
async def get_export_errors(
    export_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("exports.view")),
    db: AsyncSession = Depends(get_db),
):
    await exports_repo.get_export_or_raise(db, export_id)
    errors = await exports_repo.list_errors_for_export(db, export_id)
    return ExportErrorListResponse(
        errors=[ExportErrorResponse(lead_id=e.lead_id, message=e.message) for e in errors]
    )


@router.get("/{export_id}/download", response_model=ExportDownloadResponse)
async def download_export(
    export_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("exports.view")),
    db: AsyncSession = Depends(get_db),
):
    export = await exports_repo.get_export_or_raise(db, export_id)
    url, expires_in_seconds, filename = await services.get_download_url(db, export)
    return ExportDownloadResponse(url=url, expires_in_seconds=expires_in_seconds, filename=filename)
