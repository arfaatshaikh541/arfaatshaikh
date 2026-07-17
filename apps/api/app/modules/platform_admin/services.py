"""Support-access grant lifecycle.

A grant is time-boxed (has an `expires_at`), reason-logged, and revocable.
It is not standing impersonation - it does not itself elevate any write
permission; it only records that a platform user is authorized to read a
specific tenant's data for support purposes during the grant window (the
actual read-scoped endpoints that consult this grant are a later
milestone's concern - Milestone 1 delivers the grant/revoke lifecycle and
the mandatory audit trail).

Both grant and revoke run inside `set_platform_bypass` because writing
the SupportAccessGrant row itself is a cross-tenant, platform-initiated
action against a tenant the platform user is not a member of.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import set_platform_bypass, set_tenant_context
from app.core.exceptions import ConflictError, ResourceNotFoundError
from app.modules.audit.service import record_audit_event, record_platform_audit_event
from app.modules.platform_admin import repositories as repo


async def grant_support_access(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    platform_user_id: uuid.UUID,
    granted_by_user_id: uuid.UUID,
    reason: str,
    duration_hours: int = 8,
):
    await set_platform_bypass(session)
    await set_tenant_context(session, tenant_id)

    expires_at = datetime.now(UTC) + timedelta(hours=duration_hours)
    grant = await repo.create_support_access_grant(
        session,
        tenant_id=tenant_id,
        platform_user_id=platform_user_id,
        reason=reason,
        granted_by_user_id=granted_by_user_id,
        expires_at=expires_at,
    )

    await record_platform_audit_event(
        session,
        actor_user_id=granted_by_user_id,
        action="support_access.granted",
        tenant_id=tenant_id,
        resource_type="support_access_grant",
        resource_id=str(grant.id),
        metadata={
            "platform_user_id": str(platform_user_id),
            "reason": reason,
            "duration_hours": duration_hours,
        },
    )
    await record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=None,
        action="support_access.granted_by_platform",
        resource_type="support_access_grant",
        resource_id=str(grant.id),
        metadata={"reason": reason},
    )
    return grant


async def revoke_support_access(
    session: AsyncSession, *, grant_id: uuid.UUID, revoked_by_user_id: uuid.UUID
):
    # Which tenant this grant belongs to is exactly what looking it up by
    # its own id would tell us, so - like the invitation-accept flow - the
    # bypass must be set before the very first lookup, not after. Safe
    # because the lookup is keyed by a unique grant_id, never a bulk scan.
    await set_platform_bypass(session)
    grant = await repo.get_support_access_grant(session, grant_id)
    if grant is None:
        raise ResourceNotFoundError("Support access grant not found.")
    if grant.revoked_at is not None:
        raise ConflictError("This grant has already been revoked.")

    await set_tenant_context(session, grant.tenant_id)

    grant.revoked_at = datetime.now(UTC)

    await record_platform_audit_event(
        session,
        actor_user_id=revoked_by_user_id,
        action="support_access.revoked",
        tenant_id=grant.tenant_id,
        resource_type="support_access_grant",
        resource_id=str(grant.id),
    )
    return grant
