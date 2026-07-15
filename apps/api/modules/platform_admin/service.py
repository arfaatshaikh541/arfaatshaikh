from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import NotFoundError
from db.session import set_tenant_context
from modules.platform_admin.models import SupportAccessGrant


def _now() -> datetime:
    return datetime.now(UTC)


async def create_grant(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    platform_user_id: uuid.UUID,
    reason: str,
    duration_hours: int,
) -> SupportAccessGrant:
    """Milestone 1 foundation: grants activate immediately for the
    requesting platform user (who already holds `platform.support_access`)
    rather than requiring a second approver — see
    docs/project-status.md 'known limitations'. Every grant is still
    time-boxed, audited, revocable, and visible to the tenant."""
    await set_tenant_context(session, tenant_id, is_platform_admin=True)
    grant = SupportAccessGrant(
        tenant_id=tenant_id,
        platform_user_id=platform_user_id,
        requested_by_user_id=platform_user_id,
        approved_by_user_id=platform_user_id,
        reason=reason,
        status="active",
        starts_at=_now(),
        expires_at=_now() + timedelta(hours=duration_hours),
    )
    session.add(grant)
    await session.flush()
    return grant


async def revoke_grant(
    session: AsyncSession, *, grant_id: uuid.UUID, tenant_id: uuid.UUID, revoked_reason: str
) -> SupportAccessGrant:
    await set_tenant_context(session, tenant_id, is_platform_admin=True)
    grant = (
        await session.execute(
            select(SupportAccessGrant).where(
                SupportAccessGrant.id == grant_id, SupportAccessGrant.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if grant is None:
        raise NotFoundError("Support access grant not found.")

    grant.status = "revoked"
    grant.revoked_at = _now()
    grant.revoked_reason = revoked_reason
    await session.flush()
    return grant


async def is_grant_active(
    session: AsyncSession, *, tenant_id: uuid.UUID, platform_user_id: uuid.UUID
) -> bool:
    await set_tenant_context(session, tenant_id, is_platform_admin=True)
    grant = (
        await session.execute(
            select(SupportAccessGrant).where(
                SupportAccessGrant.tenant_id == tenant_id,
                SupportAccessGrant.platform_user_id == platform_user_id,
                SupportAccessGrant.status == "active",
                SupportAccessGrant.expires_at > _now(),
            )
        )
    ).scalar_one_or_none()
    return grant is not None


async def list_grants_for_tenant(session: AsyncSession, *, tenant_id: uuid.UUID) -> list[SupportAccessGrant]:
    await set_tenant_context(session, tenant_id)
    result = await session.execute(
        select(SupportAccessGrant).where(SupportAccessGrant.tenant_id == tenant_id)
    )
    return list(result.scalars().all())
