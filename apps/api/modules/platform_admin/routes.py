from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import (
    PlatformContext,
    TenantContext,
    get_platform_admin_db,
    get_tenant_db,
    require_csrf,
    require_permission,
    require_platform_permission,
)
from db.session import get_db
from modules.audit import service as audit_service
from modules.platform_admin import service as platform_service
from modules.platform_admin.schemas import (
    PlatformAuditLogRead,
    SupportAccessGrantCreateRequest,
    SupportAccessGrantRead,
    TenantSummaryRead,
    UpdateTenantStatusRequest,
)

router = APIRouter(prefix="/api/platform", tags=["platform_admin"])
tenant_router = APIRouter(prefix="/api", tags=["support_access"])


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
        action="platform.support_access_granted",
        target_type="support_access_grant",
        target_id=str(grant.id),
        context={"reason": payload.reason, "duration_hours": payload.duration_hours},
    )
    await db.commit()
    return SupportAccessGrantRead.model_validate(grant)


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
    return SupportAccessGrantRead.model_validate(grant)


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
    return [SupportAccessGrantRead.model_validate(g) for g in grants]
