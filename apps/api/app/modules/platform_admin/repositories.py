import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform_admin.models import SupportAccessGrant
from app.modules.tenancy.models import Tenant


async def list_all_tenants(session: AsyncSession) -> list[Tenant]:
    stmt = select(Tenant).order_by(Tenant.created_at.desc())
    return list((await session.execute(stmt)).scalars().all())


async def create_support_access_grant(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    platform_user_id: uuid.UUID,
    reason: str,
    granted_by_user_id: uuid.UUID,
    expires_at,
) -> SupportAccessGrant:
    grant = SupportAccessGrant(
        tenant_id=tenant_id,
        platform_user_id=platform_user_id,
        reason=reason,
        granted_by_user_id=granted_by_user_id,
        expires_at=expires_at,
    )
    session.add(grant)
    await session.flush()
    return grant


async def get_support_access_grant(
    session: AsyncSession, grant_id: uuid.UUID
) -> SupportAccessGrant | None:
    stmt = select(SupportAccessGrant).where(SupportAccessGrant.id == grant_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_support_access_grants_for_tenant(
    session: AsyncSession, tenant_id: uuid.UUID
) -> list[SupportAccessGrant]:
    stmt = (
        select(SupportAccessGrant)
        .where(SupportAccessGrant.tenant_id == tenant_id)
        .order_by(SupportAccessGrant.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())
