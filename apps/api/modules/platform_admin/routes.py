from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import (
    PlatformContext,
    TenantContext,
    get_tenant_db,
    require_csrf,
    require_permission,
    require_platform_permission,
)
from db.session import get_db
from modules.audit import service as audit_service
from modules.platform_admin import service as platform_service
from modules.platform_admin.schemas import SupportAccessGrantCreateRequest, SupportAccessGrantRead

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
