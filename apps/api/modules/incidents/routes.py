from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import TenantContext, get_tenant_db, require_csrf, require_permission, require_tenant_write
from modules.assets.models import Asset
from modules.audit import service as audit_service
from modules.findings.models import Finding
from modules.incidents import service as incidents_service
from modules.incidents.models import Incident
from modules.incidents.schemas import (
    AddIncidentNoteRequest,
    CloseIncidentRequest,
    DeclareIncidentRequest,
    IncidentActivityRead,
    IncidentDetail,
    IncidentListItem,
    IncidentSummaryRead,
    LinkAssetRequest,
    LinkedAssetRead,
    LinkedFindingRead,
    LinkFindingRequest,
    UpdateIncidentRequest,
    UpdateIncidentStatusRequest,
)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


def _to_detail(
    incident: Incident,
    findings_rows: list[tuple[Finding, str]],
    assets_rows: list[tuple[Asset, str]],
) -> IncidentDetail:
    base = incidents_service.to_incident_list_item(incident, len(findings_rows), len(assets_rows))
    return IncidentDetail(
        **base.model_dump(),
        description=incident.description,
        declared_by_user_id=incident.declared_by_user_id,
        closure_summary=incident.closure_summary,
        findings=[
            LinkedFindingRead(
                id=f.id, title=f.title, rule_key=f.rule_key, severity=f.severity, status=f.status,
                asset_display_name=asset_name,
            )
            for f, asset_name in findings_rows
        ],
        assets=[
            LinkedAssetRead(
                id=a.id, display_name=a.display_name, asset_type=asset_type_key, criticality=a.criticality
            )
            for a, asset_type_key in assets_rows
        ],
    )


@router.get("", response_model=list[IncidentListItem])
async def list_incidents(
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("incidents.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[IncidentListItem]:
    rows = await incidents_service.list_incidents(
        db, tenant_id=ctx.tenant_id, status=status, severity=severity
    )
    return [incidents_service.to_incident_list_item(incident, fc, ac) for incident, fc, ac in rows]


@router.get("/summary", response_model=IncidentSummaryRead)
async def get_incident_summary(
    ctx: TenantContext = Depends(require_permission("incidents.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> IncidentSummaryRead:
    summary = await incidents_service.get_incident_summary(db, tenant_id=ctx.tenant_id)
    return IncidentSummaryRead(**summary)


@router.get("/{incident_id}", response_model=IncidentDetail)
async def get_incident(
    incident_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("incidents.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> IncidentDetail:
    incident, findings_rows, assets_rows = await incidents_service.get_incident_detail(
        db, tenant_id=ctx.tenant_id, incident_id=incident_id
    )
    return _to_detail(incident, findings_rows, assets_rows)


@router.get("/{incident_id}/activity", response_model=list[IncidentActivityRead])
async def get_incident_activity(
    incident_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("incidents.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[IncidentActivityRead]:
    entries = await audit_service.list_for_target(
        db, tenant_id=ctx.tenant_id, target_type="incident", target_id=str(incident_id)
    )
    return [
        IncidentActivityRead(
            actor_label=e.actor_label, action=e.action, context=e.context, created_at=e.created_at
        )
        for e in entries
    ]


@router.post("", response_model=IncidentDetail, dependencies=[Depends(require_csrf)])
async def declare_incident(
    payload: DeclareIncidentRequest,
    ctx: TenantContext = Depends(require_permission("incidents.declare")),
    db: AsyncSession = Depends(get_tenant_db),
) -> IncidentDetail:
    require_tenant_write(ctx)
    incident = await incidents_service.declare_incident(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        finding_ids=payload.finding_ids,
        asset_ids=payload.asset_ids,
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="incidents.declared",
        target_type="incident",
        target_id=str(incident.id),
        context={"title": payload.title, "severity": payload.severity},
    )
    _, findings_rows, assets_rows = await incidents_service.get_incident_detail(
        db, tenant_id=ctx.tenant_id, incident_id=incident.id
    )
    response = _to_detail(incident, findings_rows, assets_rows)
    await db.commit()
    return response


@router.patch("/{incident_id}", response_model=IncidentDetail, dependencies=[Depends(require_csrf)])
async def update_incident(
    incident_id: uuid.UUID,
    payload: UpdateIncidentRequest,
    ctx: TenantContext = Depends(require_permission("incidents.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> IncidentDetail:
    require_tenant_write(ctx)
    await incidents_service.update_incident(
        db,
        tenant_id=ctx.tenant_id,
        incident_id=incident_id,
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        assigned_to_user_id=payload.assigned_to_user_id,
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="incidents.updated",
        target_type="incident",
        target_id=str(incident_id),
    )
    incident, findings_rows, assets_rows = await incidents_service.get_incident_detail(
        db, tenant_id=ctx.tenant_id, incident_id=incident_id
    )
    response = _to_detail(incident, findings_rows, assets_rows)
    await db.commit()
    return response


@router.patch("/{incident_id}/status", response_model=IncidentDetail, dependencies=[Depends(require_csrf)])
async def update_incident_status(
    incident_id: uuid.UUID,
    payload: UpdateIncidentStatusRequest,
    ctx: TenantContext = Depends(require_permission("incidents.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> IncidentDetail:
    require_tenant_write(ctx)
    await incidents_service.update_status(
        db, tenant_id=ctx.tenant_id, incident_id=incident_id, status=payload.status
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="incidents.status_changed",
        target_type="incident",
        target_id=str(incident_id),
        context={"status": payload.status},
    )
    incident, findings_rows, assets_rows = await incidents_service.get_incident_detail(
        db, tenant_id=ctx.tenant_id, incident_id=incident_id
    )
    response = _to_detail(incident, findings_rows, assets_rows)
    await db.commit()
    return response


@router.post("/{incident_id}/notes", response_model=IncidentDetail, dependencies=[Depends(require_csrf)])
async def add_incident_note(
    incident_id: uuid.UUID,
    payload: AddIncidentNoteRequest,
    ctx: TenantContext = Depends(require_permission("incidents.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> IncidentDetail:
    require_tenant_write(ctx)
    await incidents_service.get_incident_or_404(db, tenant_id=ctx.tenant_id, incident_id=incident_id)
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="incidents.note_added",
        target_type="incident",
        target_id=str(incident_id),
        context={"message": payload.message},
    )
    incident, findings_rows, assets_rows = await incidents_service.get_incident_detail(
        db, tenant_id=ctx.tenant_id, incident_id=incident_id
    )
    response = _to_detail(incident, findings_rows, assets_rows)
    await db.commit()
    return response


@router.post(
    "/{incident_id}/link-finding", response_model=IncidentDetail, dependencies=[Depends(require_csrf)]
)
async def link_finding(
    incident_id: uuid.UUID,
    payload: LinkFindingRequest,
    ctx: TenantContext = Depends(require_permission("incidents.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> IncidentDetail:
    require_tenant_write(ctx)
    await incidents_service.link_finding(
        db, tenant_id=ctx.tenant_id, incident_id=incident_id, finding_id=payload.finding_id
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="incidents.finding_linked",
        target_type="incident",
        target_id=str(incident_id),
        context={"finding_id": str(payload.finding_id)},
    )
    incident, findings_rows, assets_rows = await incidents_service.get_incident_detail(
        db, tenant_id=ctx.tenant_id, incident_id=incident_id
    )
    response = _to_detail(incident, findings_rows, assets_rows)
    await db.commit()
    return response


@router.post("/{incident_id}/link-asset", response_model=IncidentDetail, dependencies=[Depends(require_csrf)])
async def link_asset(
    incident_id: uuid.UUID,
    payload: LinkAssetRequest,
    ctx: TenantContext = Depends(require_permission("incidents.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> IncidentDetail:
    require_tenant_write(ctx)
    await incidents_service.link_asset(
        db, tenant_id=ctx.tenant_id, incident_id=incident_id, asset_id=payload.asset_id
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="incidents.asset_linked",
        target_type="incident",
        target_id=str(incident_id),
        context={"asset_id": str(payload.asset_id)},
    )
    incident, findings_rows, assets_rows = await incidents_service.get_incident_detail(
        db, tenant_id=ctx.tenant_id, incident_id=incident_id
    )
    response = _to_detail(incident, findings_rows, assets_rows)
    await db.commit()
    return response


@router.post("/{incident_id}/close", response_model=IncidentDetail, dependencies=[Depends(require_csrf)])
async def close_incident(
    incident_id: uuid.UUID,
    payload: CloseIncidentRequest,
    ctx: TenantContext = Depends(require_permission("incidents.close")),
    db: AsyncSession = Depends(get_tenant_db),
) -> IncidentDetail:
    require_tenant_write(ctx)
    await incidents_service.close_incident(
        db, tenant_id=ctx.tenant_id, incident_id=incident_id, closure_summary=payload.closure_summary
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="incidents.closed",
        target_type="incident",
        target_id=str(incident_id),
        context={"closure_summary": payload.closure_summary},
    )
    incident, findings_rows, assets_rows = await incidents_service.get_incident_detail(
        db, tenant_id=ctx.tenant_id, incident_id=incident_id
    )
    response = _to_detail(incident, findings_rows, assets_rows)
    await db.commit()
    return response


@router.post("/{incident_id}/reopen", response_model=IncidentDetail, dependencies=[Depends(require_csrf)])
async def reopen_incident(
    incident_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("incidents.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> IncidentDetail:
    require_tenant_write(ctx)
    await incidents_service.reopen_incident(db, tenant_id=ctx.tenant_id, incident_id=incident_id)
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="incidents.reopened",
        target_type="incident",
        target_id=str(incident_id),
    )
    incident, findings_rows, assets_rows = await incidents_service.get_incident_detail(
        db, tenant_id=ctx.tenant_id, incident_id=incident_id
    )
    response = _to_detail(incident, findings_rows, assets_rows)
    await db.commit()
    return response
