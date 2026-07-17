from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import (
    TenantContext,
    get_tenant_context,
    get_tenant_db,
    require_csrf,
    require_permission,
    require_tenant_write,
)
from core.errors import AuthorizationError
from modules.audit import service as audit_service
from modules.compliance import service as compliance_service
from modules.compliance.models import EvidenceRecord
from modules.compliance.schemas import (
    ComplianceSummaryRead,
    ControlRead,
    CreateEvidenceRequest,
    EvidenceExportRead,
    EvidenceRead,
    FrameworkRead,
    UpdateControlStatusRequest,
)
from modules.compliance.service import TARGET_MANAGE_PERMISSION

compliance_router = APIRouter(prefix="/api/compliance", tags=["compliance"])
evidence_router = APIRouter(prefix="/api/evidence", tags=["evidence"])


def _to_evidence_read(evidence: EvidenceRecord) -> EvidenceRead:
    return EvidenceRead(
        id=evidence.id,
        title=evidence.title,
        description=evidence.description,
        evidence_type=evidence.evidence_type,
        source_url=evidence.source_url,
        target_type=evidence.target_type,
        target_id=evidence.target_id,
        collected_at=evidence.collected_at,
        created_by_user_id=evidence.created_by_user_id,
        created_at=evidence.created_at,
        file_name=evidence.file_name,
        file_content_type=evidence.file_content_type,
        file_size_bytes=evidence.file_size_bytes,
    )


@compliance_router.get("/frameworks", response_model=list[FrameworkRead])
async def list_frameworks(
    ctx: TenantContext = Depends(require_permission("compliance.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[FrameworkRead]:
    frameworks = await compliance_service.list_frameworks_with_status(db, tenant_id=ctx.tenant_id)
    return [
        FrameworkRead(
            id=f["id"], key=f["key"], name=f["name"], description=f["description"], score=f["score"],
            controls=[ControlRead(**c) for c in f["controls"]],
        )
        for f in frameworks
    ]


@compliance_router.get("/summary", response_model=ComplianceSummaryRead)
async def get_summary(
    ctx: TenantContext = Depends(require_permission("compliance.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> ComplianceSummaryRead:
    summary = await compliance_service.get_compliance_summary(db, tenant_id=ctx.tenant_id)
    return ComplianceSummaryRead(**summary)


@compliance_router.patch(
    "/controls/{control_id}", response_model=ControlRead, dependencies=[Depends(require_csrf)]
)
async def update_control_status(
    control_id: uuid.UUID,
    payload: UpdateControlStatusRequest,
    ctx: TenantContext = Depends(require_permission("compliance.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> ControlRead:
    require_tenant_write(ctx)
    await compliance_service.update_control_status(
        db,
        tenant_id=ctx.tenant_id,
        control_id=control_id,
        status=payload.status,
        note=payload.note,
        actor_user_id=ctx.user.id,
    )
    control_row = await compliance_service.get_control_detail(
        db, tenant_id=ctx.tenant_id, control_id=control_id
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="compliance.control_status_updated",
        target_type="compliance_control",
        target_id=str(control_id),
        context={"status": payload.status},
    )
    response = ControlRead(**control_row)
    await db.commit()
    return response


@evidence_router.get("", response_model=list[EvidenceRead])
async def list_evidence(
    target_type: str = Query(...),
    target_id: uuid.UUID = Query(...),
    ctx: TenantContext = Depends(require_permission("evidence.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[EvidenceRead]:
    rows = await compliance_service.list_evidence(
        db, tenant_id=ctx.tenant_id, target_type=target_type, target_id=target_id
    )
    return [_to_evidence_read(e) for e in rows]


@evidence_router.get("/export", response_model=EvidenceExportRead)
async def export_evidence(
    target_type: str = Query(...),
    target_id: uuid.UUID = Query(...),
    ctx: TenantContext = Depends(require_permission("evidence.export")),
    db: AsyncSession = Depends(get_tenant_db),
) -> EvidenceExportRead:
    rows = await compliance_service.list_evidence(
        db, tenant_id=ctx.tenant_id, target_type=target_type, target_id=target_id
    )
    return EvidenceExportRead(
        target_type=target_type,
        target_id=target_id,
        generated_at=datetime.now(UTC),
        evidence=[_to_evidence_read(e) for e in rows],
    )


@evidence_router.post("", response_model=EvidenceRead, dependencies=[Depends(require_csrf)])
async def create_evidence(
    payload: CreateEvidenceRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_tenant_db),
) -> EvidenceRead:
    require_tenant_write(ctx)
    required_permission = TARGET_MANAGE_PERMISSION[payload.target_type]
    if not ctx.has_permission(required_permission):
        raise AuthorizationError(
            f"Your role does not have the '{required_permission}' permission.",
            details={"required_permission": required_permission},
        )
    evidence = await compliance_service.create_evidence(
        db,
        tenant_id=ctx.tenant_id,
        title=payload.title,
        description=payload.description,
        evidence_type=payload.evidence_type,
        source_url=payload.source_url,
        target_type=payload.target_type,
        target_id=payload.target_id,
        collected_at=payload.collected_at,
        created_by_user_id=ctx.user.id,
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="evidence.recorded",
        target_type=payload.target_type,
        target_id=str(payload.target_id),
        context={"evidence_id": str(evidence.id), "title": payload.title},
    )
    response = _to_evidence_read(evidence)
    await db.commit()
    return response


@evidence_router.post("/document", response_model=EvidenceRead, dependencies=[Depends(require_csrf)])
async def create_document_evidence(
    title: str = Form(..., min_length=2, max_length=300),
    description: str = Form(default=""),
    target_type: str = Form(..., pattern="^(compliance_control|incident)$"),
    target_id: uuid.UUID = Form(...),
    collected_at: datetime | None = Form(default=None),
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_tenant_db),
) -> EvidenceRead:
    require_tenant_write(ctx)
    required_permission = TARGET_MANAGE_PERMISSION[target_type]
    if not ctx.has_permission(required_permission):
        raise AuthorizationError(
            f"Your role does not have the '{required_permission}' permission.",
            details={"required_permission": required_permission},
        )
    content = await file.read()
    evidence = await compliance_service.create_document_evidence(
        db,
        tenant_id=ctx.tenant_id,
        title=title,
        description=description,
        target_type=target_type,
        target_id=target_id,
        collected_at=collected_at,
        created_by_user_id=ctx.user.id,
        filename=file.filename or "upload",
        content_type=file.content_type,
        content=content,
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="evidence.recorded",
        target_type=target_type,
        target_id=str(target_id),
        context={"evidence_id": str(evidence.id), "title": title, "file_name": evidence.file_name},
    )
    response = _to_evidence_read(evidence)
    await db.commit()
    return response


@evidence_router.get("/{evidence_id}/file")
async def download_evidence_file(
    evidence_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("evidence.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> Response:
    evidence, content = await compliance_service.get_evidence_file(
        db, tenant_id=ctx.tenant_id, evidence_id=evidence_id
    )
    return Response(
        content=content,
        media_type=evidence.file_content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{evidence.file_name}"'},
    )


@evidence_router.delete("/{evidence_id}", dependencies=[Depends(require_csrf)])
async def delete_evidence(
    evidence_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    require_tenant_write(ctx)
    evidence = await compliance_service.get_evidence_or_404(
        db, tenant_id=ctx.tenant_id, evidence_id=evidence_id
    )
    required_permission = TARGET_MANAGE_PERMISSION[evidence.target_type]
    if not ctx.has_permission(required_permission):
        raise AuthorizationError(
            f"Your role does not have the '{required_permission}' permission.",
            details={"required_permission": required_permission},
        )
    await compliance_service.delete_evidence(db, tenant_id=ctx.tenant_id, evidence_id=evidence_id)
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="evidence.deleted",
        target_type=evidence.target_type,
        target_id=str(evidence.target_id),
        context={"evidence_id": str(evidence_id)},
    )
    await db.commit()
    return {"status": "ok"}
