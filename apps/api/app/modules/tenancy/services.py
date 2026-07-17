"""Tenant onboarding, invitations, and tenant-switching services.

`create_tenant_for_user` is the single place a new tenant comes into
existence: it creates the Tenant row, immediately establishes the RLS
tenant context for the rest of the transaction (`set_tenant_context`),
seeds the tenant's default roles/permissions from the shared catalog,
creates the Owner membership for the requesting user, provisions a credit
wallet, assigns the default trial subscription plan, and writes an audit
record - all inside one transaction so a failure partway through rolls
back the entire tenant rather than leaving an inconsistent half-created
tenant behind.
"""

import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import set_platform_bypass, set_tenant_context
from app.core.exceptions import (
    ConflictError,
    ResourceNotFoundError,
    TenantAccessDeniedError,
    ValidationAppError,
)
from app.core.mail import send_email
from app.core.security import generate_opaque_token, hash_token
from app.modules.audit.service import record_audit_event
from app.modules.entitlements.service import check_limit
from app.modules.identity.models import User
from app.modules.permissions import repositories as perm_repo
from app.modules.permissions.catalog import TENANT_ROLE_DEFAULTS
from app.modules.subscriptions import repositories as sub_repo
from app.modules.tenancy import repositories as repo
from app.modules.tenancy.models import Invitation, Membership, Tenant
from app.modules.usage.services import ensure_wallet, grant_credits


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return base or "tenant"


async def _unique_slug(session: AsyncSession, name: str) -> str:
    base_slug = _slugify(name)
    slug = base_slug
    attempt = 0
    while await repo.get_tenant_by_slug(session, slug) is not None:
        attempt += 1
        slug = f"{base_slug}-{secrets.token_hex(2)}"
        if attempt > 10:
            raise ConflictError(
                "Could not generate a unique tenant identifier. Try a different name."
            )
    return slug


async def seed_default_roles_and_permissions(
    session: AsyncSession, tenant_id: uuid.UUID
) -> dict[str, uuid.UUID]:
    all_permissions = await perm_repo.get_all_permissions(session)
    permission_id_by_key = {p.key: p.id for p in all_permissions}
    role_ids: dict[str, uuid.UUID] = {}

    for role_name, permission_keys in TENANT_ROLE_DEFAULTS.items():
        role = await perm_repo.create_role(
            session,
            tenant_id=tenant_id,
            name=role_name,
            description=f"{role_name} (default tenant role)",
            is_platform_role=False,
        )
        role_ids[role_name] = role.id
        grant_ids = [permission_id_by_key[k] for k in permission_keys if k in permission_id_by_key]
        await perm_repo.grant_permissions_to_role(
            session, role_id=role.id, tenant_id=tenant_id, permission_ids=grant_ids
        )
    return role_ids


async def create_tenant_for_user(session: AsyncSession, *, user: User, tenant_name: str) -> Tenant:
    if not tenant_name or not tenant_name.strip():
        raise ValidationAppError("Tenant name is required.")

    slug = await _unique_slug(session, tenant_name)
    tenant = await repo.create_tenant(session, name=tenant_name.strip(), slug=slug, status="trial")

    # From this point on, every insert in this transaction must belong to
    # `tenant.id` - RLS's WITH CHECK policy enforces that structurally.
    await set_tenant_context(session, tenant.id)

    await repo.create_tenant_settings(session, tenant_id=tenant.id)

    role_ids = await seed_default_roles_and_permissions(session, tenant.id)
    owner_role_id = role_ids["Owner"]

    await repo.create_membership(
        session, tenant_id=tenant.id, user_id=user.id, role_id=owner_role_id
    )

    await ensure_wallet(session, tenant.id)

    trial_plan = await sub_repo.get_plan_by_key(session, "trial")
    if trial_plan is not None:
        now = datetime.now(UTC)
        await sub_repo.create_tenant_subscription(
            session,
            tenant_id=tenant.id,
            plan_id=trial_plan.id,
            current_period_start=now,
            current_period_end=now + timedelta(days=14),
        )
        if trial_plan.monthly_credit_grant > 0:
            await grant_credits(
                session,
                tenant_id=tenant.id,
                amount=float(trial_plan.monthly_credit_grant),
                type_="grant_recurring",
                reference=f"plan:{trial_plan.key}:initial_grant",
            )

    await record_audit_event(
        session,
        tenant_id=tenant.id,
        actor_user_id=user.id,
        action="tenant.created",
        resource_type="tenant",
        resource_id=str(tenant.id),
        metadata={"name": tenant.name, "slug": tenant.slug},
    )
    return tenant


async def list_my_memberships(session: AsyncSession, user_id: uuid.UUID) -> list[Membership]:
    """Lists a user's own memberships across every tenant they belong to -
    e.g. for auto-selecting the active tenant at login, or populating the
    tenant-switcher UI. Requires `set_platform_bypass` because the whole
    point is reading across tenant boundaries; it is safe because the
    query is filtered to `user_id == this authenticated user's own id`, so
    it can never surface another user's or another tenant's data beyond
    the fact that this user is a member of it."""
    await set_platform_bypass(session)
    return await repo.get_active_memberships_for_user(session, user_id)


async def switch_active_tenant(
    session: AsyncSession, *, user: User, session_row, requested_tenant_id: uuid.UUID
) -> Tenant:
    """The client supplies which tenant it *wants* to switch to, but that
    value is only ever used as a lookup key here - it is authorized against
    the caller's real, server-recorded memberships before being trusted.

    The RLS tenant-context GUC must be set to `requested_tenant_id` before
    this lookup runs, or the membership row (which lives in a strictly
    RLS-protected table) would be invisible even when it genuinely exists.
    This is safe: it only ever makes the *requested* tenant's own rows
    visible for a query that is itself already filtered to that tenant_id
    and this user_id - it grants no broader access.
    """
    await set_tenant_context(session, requested_tenant_id)
    membership = await repo.get_membership(session, tenant_id=requested_tenant_id, user_id=user.id)
    if membership is None or membership.status != "active":
        raise TenantAccessDeniedError("You are not an active member of the requested tenant.")

    tenant = await repo.get_tenant_by_id(session, requested_tenant_id)
    if tenant is None:
        raise ResourceNotFoundError("Tenant not found.")
    if tenant.status == "archived":
        raise TenantAccessDeniedError("This tenant has been archived.")

    session_row.active_tenant_id = tenant.id
    return tenant


async def create_invitation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    invited_by_user_id: uuid.UUID,
    email: str,
    role_id: uuid.UUID,
) -> Invitation:
    role = await perm_repo.get_role_by_id(session, role_id)
    if role is None or role.tenant_id != tenant_id:
        raise ValidationAppError("The selected role does not belong to this tenant.")

    # Count both existing members and outstanding invitations against the
    # plan limit - otherwise a tenant could send unlimited invitations and
    # only get blocked once enough of them are accepted.
    current_member_count = await repo.count_active_memberships(session, tenant_id)
    pending_invitation_count = await repo.count_pending_invitations(session, tenant_id)
    await check_limit(
        session, tenant_id, "max_team_members", current_member_count + pending_invitation_count
    )

    settings = get_settings()
    raw_token = generate_opaque_token()
    expires_at = datetime.now(UTC) + timedelta(days=settings.invitation_token_ttl_days)

    invitation = await repo.create_invitation(
        session,
        tenant_id=tenant_id,
        email=email,
        role_id=role_id,
        invited_by_user_id=invited_by_user_id,
        token_hash=hash_token(raw_token),
        expires_at=expires_at,
    )

    accept_url = f"{settings.api_base_url}/invitations/accept?token={raw_token}"
    await send_email(
        to_email=email,
        subject="You've been invited to a GRIDKEEP workspace",
        text_body=f"Accept your invitation by visiting: {accept_url}",
        html_body=f'<p><a href="{accept_url}">Accept your invitation</a></p>',
    )

    await record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=invited_by_user_id,
        action="invitation.created",
        resource_type="invitation",
        resource_id=str(invitation.id),
        metadata={"email": email, "role_id": str(role_id)},
    )
    return invitation


async def accept_invitation(session: AsyncSession, *, raw_token: str, user: User) -> Membership:
    # Which tenant this token belongs to is exactly what we're trying to
    # discover, so no tenant GUC can be set yet - `set_platform_bypass` is
    # the narrow, audited escape hatch for this one case. It is safe here
    # because the lookup is keyed by a unique, unguessable, single-use,
    # expiring hashed token: it can only ever return the single invitation
    # matching that exact token, never a bulk cross-tenant result.
    await set_platform_bypass(session)
    invitation = await repo.get_invitation_by_token_hash(session, hash_token(raw_token))
    now = datetime.now(UTC)
    if invitation is None or invitation.status != "pending" or invitation.expires_at < now:
        raise ResourceNotFoundError("This invitation is invalid or has expired.")

    if invitation.email.lower() != user.email.lower():
        raise TenantAccessDeniedError("This invitation was issued to a different email address.")

    await set_tenant_context(session, invitation.tenant_id)

    existing = await repo.get_membership(session, tenant_id=invitation.tenant_id, user_id=user.id)
    if existing is not None:
        raise ConflictError("You are already a member of this tenant.")

    membership = await repo.create_membership(
        session, tenant_id=invitation.tenant_id, user_id=user.id, role_id=invitation.role_id
    )
    invitation.status = "accepted"
    invitation.accepted_at = now

    await record_audit_event(
        session,
        tenant_id=invitation.tenant_id,
        actor_user_id=user.id,
        action="invitation.accepted",
        resource_type="membership",
        resource_id=str(membership.id),
        metadata={"invitation_id": str(invitation.id)},
    )
    return membership
