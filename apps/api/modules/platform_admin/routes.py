from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import (
    PlatformContext,
    SupportAccessContext,
    TenantContext,
    get_platform_admin_db,
    get_tenant_db,
    require_csrf,
    require_permission,
    require_platform_permission,
    require_support_access_grant,
)
from db.session import get_db
from modules.audit import service as audit_service
from modules.findings import service as findings_service
from modules.findings.schemas import FindingListItem
from modules.incidents import service as incidents_service
from modules.incidents.schemas import IncidentListItem
from modules.platform_admin import service as platform_service
from modules.platform_admin.models import SupportAccessGrant
from modules.platform_admin.schemas import (
    PlatformAuditLogRead,
    SupportAccessGrantCreateRequest,
    SupportAccessGrantRead,
    TenantSummaryRead,
    TenantWorkspaceSnapshotRead,
    UpdateTenantStatusRequest,
)

router = APIRouter(prefix="/api/platform", tags=["platform_admin"])
tenant_router = APIRouter(prefix="/api", tags=["support_access"])


async def _to_grant_reads(
    db: AsyncSession, grants: list[SupportAccessGrant]
) -> list[SupportAccessGrantRead]:
    """Resolves the three actor columns to emails in one batched lookup —
    `SupportAccessGrant`'s own docstring has always promised these grants
    are tenant-visible; raw UUIDs aren't real transparency."""
    user_ids = {
        uid
        for grant in grants
        for uid in (grant.platform_user_id, grant.requested_by_user_id, grant.approved_by_user_id)
        if uid is not None
    }
    emails = await platform_service.resolve_user_emails(db, user_ids)
    return [
        SupportAccessGrantRead.model_validate(grant).model_copy(
            update={
                "platform_user_email": emails.get(grant.platform_user_id),
                "requested_by_email": emails.get(grant.requested_by_user_id),
                "approved_by_email": (
                    emails.get(grant.approved_by_user_id) if grant.approved_by_user_id else None
                ),
            }
        )
        for grant in grants
    ]


@router.post(
    "/support-access-grants",
    response_model=SupportAccessGrantRead,
    dependencies=[Depends(require_csrf)],
)
async def create_support_access_grant(
    payload: SupportAccessGrantCreateRequest,
    ctx: PlatformContext = Depends(require_platform_permission("platform.support_access")),
    db: AsyncSession = Depends(get_db),
) -> SupportAccessGrantRead:
    grant = await platform_service.create_grant(
        db,
        tenant_id=payload.tenant_id,
        platform_user_id=ctx.user.id,
        reason=payload.reason,
        duration_hours=payload.duration_hours,
    )
    await audit_service.record(
        db,
        tenant_id=payload.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=f"platform:{ctx.user.email}",
        action="platform.support_access_requested",
        target_type="support_access_grant",
        target_id=str(grant.id),
        context={"reason": payload.reason, "duration_hours": payload.duration_hours},
    )
    await db.commit()
    return (await _to_grant_reads(db, [grant]))[0]


@router.post(
    "/support-access-grants/{grant_id}/approve",
    response_model=SupportAccessGrantRead,
    dependencies=[Depends(require_csrf)],
)
async def approve_support_access_grant(
    grant_id: uuid.UUID,
    tenant_id: uuid.UUID,
    ctx: PlatformContext = Depends(require_platform_permission("platform.support_access")),
    db: AsyncSession = Depends(get_db),
) -> SupportAccessGrantRead:
    """The second-approver check this milestone exists for: `approve_grant`
    rejects the requester approving their own request."""
    grant = await platform_service.approve_grant(
        db, grant_id=grant_id, tenant_id=tenant_id, approver_user_id=ctx.user.id
    )
    await audit_service.record(
        db,
        tenant_id=tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=f"platform:{ctx.user.email}",
        action="platform.support_access_approved",
        target_type="support_access_grant",
        target_id=str(grant.id),
    )
    await db.commit()
    return (await _to_grant_reads(db, [grant]))[0]


@router.post(
    "/support-access-grants/{grant_id}/revoke",
    response_model=SupportAccessGrantRead,
    dependencies=[Depends(require_csrf)],
)
async def revoke_support_access_grant(
    grant_id: uuid.UUID,
    tenant_id: uuid.UUID,
    ctx: PlatformContext = Depends(require_platform_permission("platform.support_access")),
    db: AsyncSession = Depends(get_db),
) -> SupportAccessGrantRead:
    grant = await platform_service.revoke_grant(
        db, grant_id=grant_id, tenant_id=tenant_id, revoked_reason=f"Revoked by {ctx.user.email}"
    )
    await audit_service.record(
        db,
        tenant_id=tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=f"platform:{ctx.user.email}",
        action="platform.support_access_revoked",
        target_type="support_access_grant",
        target_id=str(grant.id),
    )
    await db.commit()
    return (await _to_grant_reads(db, [grant]))[0]


@router.get("/support-access-grants", response_model=list[SupportAccessGrantRead])
async def list_all_support_access_grants(
    tenant_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    ctx: PlatformContext = Depends(require_platform_permission("platform.support_access")),
    db: AsyncSession = Depends(get_platform_admin_db),
) -> list[SupportAccessGrantRead]:
    """The platform-wide view a second approver needs to discover pending
    requests across every tenant — only reachable through
    `get_platform_admin_db`, the one session flavour the widened
    `support_access_grants_select` RLS policy grants cross-tenant
    visibility to (the same pattern Milestone 12 used for the platform-wide
    audit log)."""
    grants = await platform_service.list_all_grants(db, tenant_id=tenant_id, status=status)
    return await _to_grant_reads(db, grants)


@router.get("/tenants", response_model=list[TenantSummaryRead])
async def list_tenants(
    ctx: PlatformContext = Depends(require_platform_permission("platform.tenants.manage")),
    db: AsyncSession = Depends(get_db),
) -> list[TenantSummaryRead]:
    tenants = await platform_service.list_tenants(db)
    return [TenantSummaryRead.model_validate(t) for t in tenants]


@router.get("/tenants/{tenant_id}", response_model=TenantSummaryRead)
async def get_tenant(
    tenant_id: uuid.UUID,
    ctx: PlatformContext = Depends(require_platform_permission("platform.tenants.manage")),
    db: AsyncSession = Depends(get_db),
) -> TenantSummaryRead:
    tenant = await platform_service.get_tenant_or_404(db, tenant_id=tenant_id)
    return TenantSummaryRead.model_validate(tenant)


@router.get("/tenants/{tenant_id}/workspace-snapshot", response_model=TenantWorkspaceSnapshotRead)
async def get_tenant_workspace_snapshot(
    tenant_id: uuid.UUID,
    ctx: SupportAccessContext = Depends(require_support_access_grant()),
    db: AsyncSession = Depends(get_db),
) -> TenantWorkspaceSnapshotRead:
    """The read this whole grant workflow exists to gate: a platform admin
    can only reach this once `require_support_access_grant` has confirmed
    they hold an active, approved grant for this exact tenant. Recorded as
    an audited "use" of the grant, not just its creation/approval/revoke —
    the model's own docstring has always promised both are audited."""
    snapshot = await platform_service.get_tenant_workspace_snapshot(db, tenant_id=tenant_id)
    await audit_service.record(
        db,
        tenant_id=tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=f"platform:{ctx.user.email}",
        action="platform.support_access_used",
        target_type="tenant",
        target_id=str(tenant_id),
        context={"view": "workspace_snapshot"},
    )
    await db.commit()
    return TenantWorkspaceSnapshotRead.model_validate(
        {**snapshot, "access_expires_at": ctx.grant_expires_at}
    )


@router.get("/tenants/{tenant_id}/findings", response_model=list[FindingListItem])
async def get_tenant_findings_for_support(
    tenant_id: uuid.UUID,
    severity: str | None = Query(default=None),
    status: str | None = Query(default=None),
    ctx: SupportAccessContext = Depends(require_support_access_grant()),
    db: AsyncSession = Depends(get_db),
) -> list[FindingListItem]:
    """Milestone 18: the drill-down Milestone 16's own Known Limitations
    named as "a natural next increment" — the workspace snapshot's
    `open_findings_total` count with no way to see what those findings
    actually are. Reuses `findings_service.list_findings` and
    `to_finding_list_item` verbatim (the same mapping the tenant-facing
    `GET /api/findings` uses) rather than re-deriving risk scoring here."""
    rows = await findings_service.list_findings(
        db, tenant_id=tenant_id, severity=severity, status=status
    )
    await audit_service.record(
        db,
        tenant_id=tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=f"platform:{ctx.user.email}",
        action="platform.support_access_used",
        target_type="tenant",
        target_id=str(tenant_id),
        context={"view": "findings", "severity": severity, "status": status},
    )
    await db.commit()
    return [findings_service.to_finding_list_item(finding, asset) for finding, asset in rows]


@router.get("/tenants/{tenant_id}/incidents", response_model=list[IncidentListItem])
async def get_tenant_incidents_for_support(
    tenant_id: uuid.UUID,
    severity: str | None = Query(default=None),
    status: str | None = Query(default=None),
    ctx: SupportAccessContext = Depends(require_support_access_grant()),
    db: AsyncSession = Depends(get_db),
) -> list[IncidentListItem]:
    """Milestone 19: the second grant-gated drill-down, extending the exact
    pattern Milestone 18 established for findings to incidents — the other
    summary-only tile Milestone 16's Known Limitations named. Reuses
    `incidents_service.list_incidents` and `to_incident_list_item`
    verbatim, the same mapping the tenant-facing `GET /api/incidents`
    uses."""
    rows = await incidents_service.list_incidents(
        db, tenant_id=tenant_id, severity=severity, status=status
    )
    await audit_service.record(
        db,
        tenant_id=tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=f"platform:{ctx.user.email}",
        action="platform.support_access_used",
        target_type="tenant",
        target_id=str(tenant_id),
        context={"view": "incidents", "severity": severity, "status": status},
    )
    await db.commit()
    return [
        incidents_service.to_incident_list_item(incident, fc, ac) for incident, fc, ac in rows
    ]


@router.post(
    "/tenants/{tenant_id}/status", response_model=TenantSummaryRead, dependencies=[Depends(require_csrf)]
)
async def update_tenant_status(
    tenant_id: uuid.UUID,
    payload: UpdateTenantStatusRequest,
    ctx: PlatformContext = Depends(require_platform_permission("platform.tenants.manage")),
    db: AsyncSession = Depends(get_db),
) -> TenantSummaryRead:
    tenant = await platform_service.update_tenant_status(
        db,
        tenant_id=tenant_id,
        new_status=payload.status,
        reason=payload.reason,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
    )
    await db.commit()
    return TenantSummaryRead.model_validate(tenant)


@router.get("/audit-logs", response_model=list[PlatformAuditLogRead])
async def list_platform_audit_logs(
    tenant_id: uuid.UUID | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: PlatformContext = Depends(require_platform_permission("platform.audit.view")),
    db: AsyncSession = Depends(get_platform_admin_db),
) -> list[PlatformAuditLogRead]:
    """The platform-wide audit trail — every tenant's history in one
    view. Only reachable through `get_platform_admin_db`, the one session
    flavour the widened `audit_logs_select` RLS policy actually grants
    cross-tenant visibility to."""
    logs = await audit_service.list_platform_wide(
        db, tenant_id=tenant_id, action=action, limit=limit, offset=offset
    )
    return [PlatformAuditLogRead.model_validate(log) for log in logs]


@tenant_router.get("/support-access-grants", response_model=list[SupportAccessGrantRead])
async def list_support_access_grants_for_my_tenant(
    ctx: TenantContext = Depends(require_permission("settings.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[SupportAccessGrantRead]:
    """Tenant-visible log of every platform support-access grant against
    this workspace — satisfies 'audit all platform support access' from
    the tenant's own side, not just the platform's."""
    grants = await platform_service.list_grants_for_tenant(db, tenant_id=ctx.tenant_id)
    return await _to_grant_reads(db, grants)
