from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import TenantContext, get_tenant_db, require_csrf, require_permission, require_tenant_write
from core.task_queue import enqueue_run_correlation
from modules.assets.models import Asset
from modules.audit import service as audit_service
from modules.findings import service as findings_service
from modules.findings.models import Finding
from modules.findings.schemas import (
    AcceptRiskRequest,
    AssignFindingRequest,
    CorrelateTriggerResponse,
    DismissFindingRequest,
    FindingActivityRead,
    FindingDetail,
    FindingListItem,
    RemediateFindingRequest,
    RiskSummaryRead,
)

router = APIRouter(prefix="/api/findings", tags=["findings"])


def _to_detail(finding: Finding, asset: Asset) -> FindingDetail:
    base = findings_service.to_finding_list_item(finding, asset)
    return FindingDetail(
        **base.model_dump(),
        description=finding.description,
        evidence=finding.evidence,
        resolution_note=finding.resolution_note,
        accepted_risk_expires_at=finding.accepted_risk_expires_at,
        closed_at=finding.closed_at,
    )


@router.get("", response_model=list[FindingListItem])
async def list_findings(
    severity: str | None = Query(default=None),
    status: str | None = Query(default=None),
    asset_id: uuid.UUID | None = Query(default=None),
    search: str | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("findings.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[FindingListItem]:
    rows = await findings_service.list_findings(
        db, tenant_id=ctx.tenant_id, severity=severity, status=status, asset_id=asset_id, search=search
    )
    return [findings_service.to_finding_list_item(finding, asset) for finding, asset in rows]


@router.get("/summary", response_model=RiskSummaryRead)
async def get_risk_summary(
    ctx: TenantContext = Depends(require_permission("findings.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> RiskSummaryRead:
    summary = await findings_service.get_risk_summary(db, tenant_id=ctx.tenant_id)
    return RiskSummaryRead(**summary)


@router.get("/{finding_id}", response_model=FindingDetail)
async def get_finding(
    finding_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("findings.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> FindingDetail:
    finding, asset = await findings_service.get_finding_detail(
        db, tenant_id=ctx.tenant_id, finding_id=finding_id
    )
    return _to_detail(finding, asset)


@router.get("/{finding_id}/activity", response_model=list[FindingActivityRead])
async def get_finding_activity(
    finding_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("findings.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[FindingActivityRead]:
    entries = await audit_service.list_for_target(
        db, tenant_id=ctx.tenant_id, target_type="finding", target_id=str(finding_id)
    )
    return [
        FindingActivityRead(
            actor_label=e.actor_label, action=e.action, context=e.context, created_at=e.created_at
        )
        for e in entries
    ]


@router.post("/{finding_id}/assign", response_model=FindingDetail, dependencies=[Depends(require_csrf)])
async def assign_finding(
    finding_id: uuid.UUID,
    payload: AssignFindingRequest,
    ctx: TenantContext = Depends(require_permission("findings.assign")),
    db: AsyncSession = Depends(get_tenant_db),
) -> FindingDetail:
    require_tenant_write(ctx)
    finding, asset = await findings_service.assign_finding(
        db, tenant_id=ctx.tenant_id, finding_id=finding_id, user_id=payload.user_id
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="findings.assigned",
        target_type="finding",
        target_id=str(finding.id),
        context={"assigned_to_user_id": str(payload.user_id)},
    )
    response = _to_detail(finding, asset)
    await db.commit()
    return response


@router.post(
    "/{finding_id}/accept-risk", response_model=FindingDetail, dependencies=[Depends(require_csrf)]
)
async def accept_risk(
    finding_id: uuid.UUID,
    payload: AcceptRiskRequest,
    ctx: TenantContext = Depends(require_permission("findings.accept_risk")),
    db: AsyncSession = Depends(get_tenant_db),
) -> FindingDetail:
    require_tenant_write(ctx)
    finding, asset = await findings_service.accept_risk(
        db,
        tenant_id=ctx.tenant_id,
        finding_id=finding_id,
        reason=payload.reason,
        expires_at=payload.expires_at,
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="findings.accepted_risk",
        target_type="finding",
        target_id=str(finding.id),
        context={
            "reason": payload.reason,
            "expires_at": str(payload.expires_at) if payload.expires_at else None,
        },
    )
    response = _to_detail(finding, asset)
    await db.commit()
    return response


@router.post("/{finding_id}/remediate", response_model=FindingDetail, dependencies=[Depends(require_csrf)])
async def remediate_finding(
    finding_id: uuid.UUID,
    payload: RemediateFindingRequest,
    ctx: TenantContext = Depends(require_permission("findings.remediate")),
    db: AsyncSession = Depends(get_tenant_db),
) -> FindingDetail:
    require_tenant_write(ctx)
    finding, asset = await findings_service.remediate_finding(
        db, tenant_id=ctx.tenant_id, finding_id=finding_id, note=payload.note
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="findings.remediated",
        target_type="finding",
        target_id=str(finding.id),
        context={"note": payload.note},
    )
    response = _to_detail(finding, asset)
    await db.commit()
    return response


@router.post("/{finding_id}/dismiss", response_model=FindingDetail, dependencies=[Depends(require_csrf)])
async def dismiss_finding(
    finding_id: uuid.UUID,
    payload: DismissFindingRequest,
    ctx: TenantContext = Depends(require_permission("findings.remediate")),
    db: AsyncSession = Depends(get_tenant_db),
) -> FindingDetail:
    require_tenant_write(ctx)
    finding, asset = await findings_service.dismiss_finding(
        db, tenant_id=ctx.tenant_id, finding_id=finding_id, reason=payload.reason
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="findings.dismissed_false_positive",
        target_type="finding",
        target_id=str(finding.id),
        context={"reason": payload.reason},
    )
    response = _to_detail(finding, asset)
    await db.commit()
    return response


@router.post("/{finding_id}/reopen", response_model=FindingDetail, dependencies=[Depends(require_csrf)])
async def reopen_finding(
    finding_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("findings.assign")),
    db: AsyncSession = Depends(get_tenant_db),
) -> FindingDetail:
    require_tenant_write(ctx)
    finding, asset = await findings_service.reopen_finding(db, tenant_id=ctx.tenant_id, finding_id=finding_id)
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="findings.reopened_manually",
        target_type="finding",
        target_id=str(finding.id),
    )
    response = _to_detail(finding, asset)
    await db.commit()
    return response


@router.post("/correlate", response_model=CorrelateTriggerResponse, dependencies=[Depends(require_csrf)])
async def trigger_correlation(
    ctx: TenantContext = Depends(require_permission("findings.remediate")),
    db: AsyncSession = Depends(get_tenant_db),
) -> CorrelateTriggerResponse:
    require_tenant_write(ctx)
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="findings.correlation_triggered",
    )
    await db.commit()
    task_id = enqueue_run_correlation(str(ctx.tenant_id))
    return CorrelateTriggerResponse(task_id=task_id)
