from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import ConflictError, NotFoundError, ValidationAppError
from db.session import set_tenant_context
from modules.audit import service as audit_service
from modules.findings import service as findings_service
from modules.identity.models import User
from modules.incidents import service as incidents_service
from modules.integrations.models import TenantIntegration
from modules.permissions.models import Membership, Role
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
    """Milestone 15: a grant now starts `pending` and stays inert —
    no `starts_at`/`expires_at`, no `approved_by_user_id` — until a
    *different* platform user approves it via `approve_grant`. Every
    grant is still time-boxed (once approved), audited, revocable, and
    visible to the tenant."""
    await set_tenant_context(session, tenant_id, is_platform_admin=True)
    grant = SupportAccessGrant(
        tenant_id=tenant_id,
        platform_user_id=platform_user_id,
        requested_by_user_id=platform_user_id,
        approved_by_user_id=None,
        reason=reason,
        status="pending",
        requested_duration_hours=duration_hours,
    )
    session.add(grant)
    await session.flush()
    return grant


async def get_grant_or_404(
    session: AsyncSession, *, grant_id: uuid.UUID, tenant_id: uuid.UUID
) -> SupportAccessGrant:
    grant = (
        await session.execute(
            select(SupportAccessGrant).where(
                SupportAccessGrant.id == grant_id, SupportAccessGrant.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if grant is None:
        raise NotFoundError("Support access grant not found.")
    return grant


async def approve_grant(
    session: AsyncSession, *, grant_id: uuid.UUID, tenant_id: uuid.UUID, approver_user_id: uuid.UUID
) -> SupportAccessGrant:
    """The second-approver check this whole milestone exists for: a grant
    can only move from `pending` to `active` here, and never by the same
    platform user who requested it in the first place."""
    await set_tenant_context(session, tenant_id, is_platform_admin=True)
    grant = await get_grant_or_404(session, grant_id=grant_id, tenant_id=tenant_id)
    if grant.status != "pending":
        raise ConflictError(f"This grant is '{grant.status}', not pending approval.")
    if grant.requested_by_user_id == approver_user_id:
        raise ValidationAppError("You cannot approve your own support access request.")

    duration_hours = grant.requested_duration_hours or 4
    grant.approved_by_user_id = approver_user_id
    grant.status = "active"
    grant.starts_at = _now()
    grant.expires_at = _now() + timedelta(hours=duration_hours)
    await session.flush()
    return grant


async def revoke_grant(
    session: AsyncSession, *, grant_id: uuid.UUID, tenant_id: uuid.UUID, revoked_reason: str
) -> SupportAccessGrant:
    """Also how a still-`pending` request is rejected before ever being
    approved — this never checked prior status, so a pending grant is
    revoked the same way an active one is."""
    await set_tenant_context(session, tenant_id, is_platform_admin=True)
    grant = await get_grant_or_404(session, grant_id=grant_id, tenant_id=tenant_id)

    grant.status = "revoked"
    grant.revoked_at = _now()
    grant.revoked_reason = revoked_reason
    await session.flush()
    return grant


async def get_active_grant(
    session: AsyncSession, *, tenant_id: uuid.UUID, platform_user_id: uuid.UUID
) -> SupportAccessGrant | None:
    """Milestone 16 named this check `is_grant_active` and only needed a
    boolean; Milestone 17's `require_support_access_grant` also needs the
    grant's own `expires_at` to surface real remaining-access time on the
    workspace snapshot, so this returns the row itself. A stale `status`
    value never matters here regardless of the Milestone 1
    `expire_support_access_grants` sweep's cadence — `expires_at > _now()`
    is checked independently of `status` on every call."""
    await set_tenant_context(session, tenant_id, is_platform_admin=True)
    return (
        await session.execute(
            select(SupportAccessGrant).where(
                SupportAccessGrant.tenant_id == tenant_id,
                SupportAccessGrant.platform_user_id == platform_user_id,
                SupportAccessGrant.status == "active",
                SupportAccessGrant.expires_at > _now(),
            )
        )
    ).scalar_one_or_none()


async def list_grants_for_tenant(session: AsyncSession, *, tenant_id: uuid.UUID) -> list[SupportAccessGrant]:
    await set_tenant_context(session, tenant_id)
    result = await session.execute(
        select(SupportAccessGrant)
        .where(SupportAccessGrant.tenant_id == tenant_id)
        .order_by(SupportAccessGrant.created_at.desc())
    )
    return list(result.scalars().all())


async def list_all_grants(
    session: AsyncSession, *, tenant_id: uuid.UUID | None = None, status: str | None = None
) -> list[SupportAccessGrant]:
    """Milestone 15: the platform-wide view a second approver needs to
    discover pending requests regardless of which tenant they target.
    Only visible through a session opened via
    `db.session.platform_admin_scoped_session` (see
    `core.deps.get_platform_admin_db`) — the widened
    `support_access_grants_select` RLS policy is what actually grants
    cross-tenant visibility here, the same pattern Milestone 12 used for
    the platform-wide audit log."""
    query = select(SupportAccessGrant)
    if tenant_id is not None:
        query = query.where(SupportAccessGrant.tenant_id == tenant_id)
    if status is not None:
        query = query.where(SupportAccessGrant.status == status)
    query = query.order_by(SupportAccessGrant.created_at.desc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_tenant_workspace_snapshot(session: AsyncSession, *, tenant_id: uuid.UUID) -> dict:
    """Milestone 16: the actual "platform_admin read of tenant data" the
    `SupportAccessGrant` docstring has referenced since Milestone 15 —
    reachable only through `core.deps.require_support_access_grant`, which
    already set `app.current_tenant_id`/`app.is_platform_admin` on this
    session as a side effect of checking the grant. Reuses the same
    per-module summary functions `modules.reporting` already composes for
    the tenant's own executive summary, rather than re-deriving "open"
    definitions here."""
    tenant = await get_tenant_or_404(session, tenant_id=tenant_id)

    members_result = await session.execute(
        select(Membership, User, Role)
        .join(User, User.id == Membership.user_id)
        .join(Role, Role.id == Membership.role_id)
        .where(Membership.tenant_id == tenant_id)
    )
    members = [
        {
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role_name": role.name,
            "status": membership.status,
        }
        for membership, user, role in members_result.all()
    ]

    risk_summary = await findings_service.get_risk_summary(session, tenant_id=tenant_id)
    incident_summary = await incidents_service.get_incident_summary(session, tenant_id=tenant_id)
    connected_integrations_count = (
        await session.execute(
            select(func.count()).select_from(TenantIntegration).where(
                TenantIntegration.tenant_id == tenant_id, TenantIntegration.status == "connected"
            )
        )
    ).scalar_one()

    return {
        "tenant_id": tenant.id,
        "tenant_name": tenant.name,
        "tenant_status": tenant.status,
        "members": members,
        "open_findings_total": risk_summary["open_findings_total"],
        "open_incidents_total": incident_summary["open_incidents_total"],
        "connected_integrations_count": connected_integrations_count,
    }


async def resolve_user_emails(session: AsyncSession, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Milestone 15: `SupportAccessGrant`'s docstring has always promised
    grants are "tenant-visible" — showing a tenant three raw user UUIDs
    (who has access, who requested it, who approved it) isn't real
    transparency. `users` carries no RLS (identity isn't tenant-owned), so
    this works from any session regardless of tenant context. A single
    batched lookup avoids one query per grant."""
    if not user_ids:
        return {}
    result = await session.execute(select(User.id, User.email).where(User.id.in_(user_ids)))
    return dict(result.all())
