from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.tenancy.models import Tenant, TenantSecurityProfile, TenantSettings


async def get_tenant_by_id(session: AsyncSession, tenant_id: uuid.UUID) -> Tenant | None:
    result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


async def slug_exists(session: AsyncSession, slug: str) -> bool:
    result = await session.execute(select(Tenant.id).where(Tenant.slug == slug))
    return result.scalar_one_or_none() is not None


async def get_settings(session: AsyncSession, tenant_id: uuid.UUID) -> TenantSettings | None:
    result = await session.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def get_security_profile(
    session: AsyncSession, tenant_id: uuid.UUID
) -> TenantSecurityProfile | None:
    result = await session.execute(
        select(TenantSecurityProfile).where(TenantSecurityProfile.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()
