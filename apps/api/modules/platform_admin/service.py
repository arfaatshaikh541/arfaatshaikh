from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import NotFoundError, ValidationAppError
from db.session import set_tenant_context
from modules.audit import service as audit_service
from modules.platform_admin.models import SupportAccessGrant
from modules.tenancy.models import Tenant

# A tenant's status transitions are a one-way-ish lifecycle, not a free
# graph: `archived` is terminal (no route back short of a fresh tenant),
# every other status can reach `suspended`/`archived` (a platform admin
# acting on non-payment or abuse) or `active` (reinstatement), and
# `read_only` exists as a softer restriction than `suspended`. A tenant
# can't "transition" to its own current status - that's a no-op, not a
# state change, and is rejected the same way.
_VALID_TENANT_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "trial": frozenset({"active", "suspended", "archived"}),
    "active": frozenset({"read_only", "suspended", "archived"}),
    "read_only": frozenset({"active", "suspended", "archived"}),
    "suspended": frozenset({"active", "read_only", "archived"}),
    "archived": frozenset(),
}


def _now() -> datetime:
    return datetime.now(UTC)


async def list_tenants(session: AsyncSession) -> list[Tenant]:
    """`tenants` carries no RLS policy of its own (see the RLS migration —
    it isn't in `_SIMPLE_TENANT_TABLES`, since it's the tenancy root, not a
    tenant-owned row), so a plain `get_db()` session already sees every
    row; no platform-admin session flavour is needed here."""
    result = await session.execute(select(Tenant).order_by(Tenant.created_at.desc()))
    return list(result.scalars().all())


async def get_tenant_or_404(session: AsyncSession, *, tenant_id: uuid.UUID) -> Tenant:
    tenant = (await session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if tenant is None:
        raise NotFoundError("Tenant not found.")
    return tenant


async def update_tenant_status(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    new_status: str,
    reason: str,
    actor_user_id: uuid.UUID,
    actor_label: str,
) -> Tenant:
    """Sets `app.is_platform_admin` on the caller's own session, scoped to
    the target tenant — the same session-variable pattern Milestone 1's
    `create_grant`/`revoke_grant` already use — so the `audit_logs_insert`
    policy (which requires `tenant_id = app_current_tenant_id()` for a
    tenant-scoped row) is satisfied when the route commits."""
    await set_tenant_context(session, tenant_id, is_platform_admin=True)
    tenant = await get_tenant_or_404(session, tenant_id=tenant_id)
    allowed = _VALID_TENANT_STATUS_TRANSITIONS.get(tenant.status, frozenset())
    if new_status not in allowed:
        raise ValidationAppError(
            f"Cannot transition a tenant from '{tenant.status}' to '{new_status}'.",
            details={"current_status": tenant.status, "requested_status": new_status},
        )
    previous_status = tenant.status
    tenant.status = new_status
    await audit_service.record(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_label=f"platform:{actor_label}",
        action="platform.tenant_status_changed",
        target_type="tenant",
        target_id=str(tenant_id),
        context={"from": previous_status, "to": new_status, "reason": reason},
    )
    await session.flush()
    return tenant


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
