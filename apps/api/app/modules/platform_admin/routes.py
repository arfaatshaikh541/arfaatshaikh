import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.dependencies import require_platform_permission, verify_csrf
from app.modules.audit.models import PlatformAuditLog
from app.modules.identity.models import User
from app.modules.platform_admin import repositories as repo
from app.modules.platform_admin import services
from app.modules.platform_admin.schemas import (
    GrantSupportAccessRequest,
    PlatformAuditLogResponse,
    SupportAccessGrantResponse,
    TenantSummary,
)

router = APIRouter(prefix="/platform", tags=["platform_admin"])


@router.get("/tenants", response_model=list[TenantSummary])
async def list_tenants(
    _user: User = Depends(require_platform_permission("platform.tenants.manage")),
    db: AsyncSession = Depends(get_db),
):
    tenants = await repo.list_all_tenants(db)
    return [
        TenantSummary(id=t.id, name=t.name, slug=t.slug, status=t.status, created_at=t.created_at)
        for t in tenants
    ]


@router.post(
    "/support-access-grants",
    response_model=SupportAccessGrantResponse,
    dependencies=[Depends(verify_csrf)],
)
async def create_support_access_grant(
    payload: GrantSupportAccessRequest,
    user: User = Depends(require_platform_permission("platform.support_access")),
    db: AsyncSession = Depends(get_db),
):
    grant = await services.grant_support_access(
        db,
        tenant_id=payload.tenant_id,
        platform_user_id=payload.platform_user_id,
        granted_by_user_id=user.id,
        reason=payload.reason,
        duration_hours=payload.duration_hours,
    )
    return SupportAccessGrantResponse(
        id=grant.id,
        tenant_id=grant.tenant_id,
        platform_user_id=grant.platform_user_id,
        reason=grant.reason,
        expires_at=grant.expires_at,
        revoked_at=grant.revoked_at,
    )


@router.post(
    "/support-access-grants/{grant_id}/revoke",
    response_model=SupportAccessGrantResponse,
    dependencies=[Depends(verify_csrf)],
)
async def revoke_support_access_grant(
    grant_id: uuid.UUID,
    user: User = Depends(require_platform_permission("platform.support_access")),
    db: AsyncSession = Depends(get_db),
):
    grant = await services.revoke_support_access(db, grant_id=grant_id, revoked_by_user_id=user.id)
    return SupportAccessGrantResponse(
        id=grant.id,
        tenant_id=grant.tenant_id,
        platform_user_id=grant.platform_user_id,
        reason=grant.reason,
        expires_at=grant.expires_at,
        revoked_at=grant.revoked_at,
    )


@router.get("/audit-logs", response_model=list[PlatformAuditLogResponse])
async def list_platform_audit_logs(
    _user: User = Depends(require_platform_permission("platform.audit.view")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(PlatformAuditLog).order_by(PlatformAuditLog.created_at.desc()).limit(200)
    logs = (await db.execute(stmt)).scalars().all()
    return [
        PlatformAuditLogResponse(
            id=log.id,
            actor_user_id=log.actor_user_id,
            action=log.action,
            tenant_id=log.tenant_id,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            created_at=log.created_at,
        )
        for log in logs
    ]
