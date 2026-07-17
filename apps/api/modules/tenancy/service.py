from __future__ import annotations

import re
import secrets
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.email import send_email
from core.errors import ConflictError, NotFoundError
from core.security import hash_password
from db.session import AsyncSessionLocal, set_tenant_context
from modules.audit import service as audit_service
from modules.identity.models import User
from modules.identity.service import issue_email_verification_token
from modules.permissions.models import Membership, Role
from modules.tenancy.models import Tenant, TenantSecurityProfile, TenantSettings
from modules.tenancy.repository import get_security_profile, get_settings, get_tenant_by_id, slug_exists
from modules.tenancy.schemas import (
    OnboardingRequest,
    OnboardingResponse,
    TenantSecurityProfileUpdate,
    TenantSettingsUpdate,
)

logger = structlog.get_logger("gridkeep.tenancy")

_SLUG_SANITIZE = re.compile(r"[^a-z0-9]+")


async def _generate_unique_slug(session: AsyncSession, organisation_name: str) -> str:
    base = _SLUG_SANITIZE.sub("-", organisation_name.strip().lower()).strip("-") or "organisation"
    base = base[:60]
    candidate = base
    while await slug_exists(session, candidate):
        candidate = f"{base}-{secrets.token_hex(3)}"
    return candidate


async def onboard_tenant(request: OnboardingRequest) -> OnboardingResponse:
    """Creates a new tenant, its first Tenant Owner user, and the owning
    membership atomically in one transaction. This is the one place in the
    codebase allowed to create tenant-owned rows before a tenant context
    exists — because it's the operation that mints that context (see
    db.session.set_tenant_context)."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            existing_user = (
                await session.execute(select(User).where(User.email == request.email))
            ).scalar_one_or_none()
            if existing_user is not None:
                raise ConflictError("An account with this email already exists.")

            tenant = Tenant(name=request.organisation_name, status="trial", is_demo=False)
            tenant.slug = await _generate_unique_slug(session, request.organisation_name)
            session.add(tenant)
            await session.flush()  # tenant.id now populated

            await set_tenant_context(session, tenant.id)

            session.add(TenantSettings(tenant_id=tenant.id, display_name=request.organisation_name))
            session.add(TenantSecurityProfile(tenant_id=tenant.id))

            owner_role = (
                await session.execute(
                    select(Role).where(Role.name == "tenant_owner", Role.is_platform_role.is_(False))
                )
            ).scalar_one_or_none()
            if owner_role is None:
                raise NotFoundError(
                    "Platform role catalogue is not initialised. Run the bootstrap seed."
                )

            user = User(
                email=request.email,
                password_hash=hash_password(request.password),
                full_name=request.full_name,
                email_verified=False,
                is_platform_user=False,
            )
            session.add(user)
            await session.flush()

            membership = Membership(
                tenant_id=tenant.id, user_id=user.id, role_id=owner_role.id, status="active"
            )
            session.add(membership)

            await audit_service.record(
                session,
                tenant_id=tenant.id,
                actor_user_id=user.id,
                actor_label=user.email,
                action="tenant.onboarded",
                target_type="tenant",
                target_id=str(tenant.id),
                context={"organisation_name": request.organisation_name},
            )

            verification_token = await issue_email_verification_token(session, user)

        send_email(
            to=user.email,
            subject="Verify your GRIDKEEP account",
            body=(
                f"Welcome to GRIDKEEP, {user.full_name}.\n\n"
                "Confirm your email address with this verification token:\n\n"
                f"{verification_token}\n\n"
                "If you did not request this account, you can ignore this message."
            ),
        )

        return OnboardingResponse(
            tenant_id=tenant.id, tenant_slug=tenant.slug, user_id=user.id
        )


async def update_settings(
    session: AsyncSession, tenant_id: uuid.UUID, payload: TenantSettingsUpdate
) -> TenantSettings:
    settings_row = await get_settings(session, tenant_id)
    if settings_row is None:
        raise NotFoundError("Tenant settings not found.")
    if payload.display_name is not None:
        settings_row.display_name = payload.display_name
    if payload.timezone is not None:
        settings_row.timezone = payload.timezone
    if payload.default_automation_mode is not None:
        settings_row.default_automation_mode = payload.default_automation_mode
    await session.flush()
    return settings_row


async def get_tenant_or_404(session: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    tenant = await get_tenant_by_id(session, tenant_id)
    if tenant is None:
        raise NotFoundError("Workspace not found.")
    return tenant


async def update_security_profile(
    session: AsyncSession, tenant_id: uuid.UUID, payload: TenantSecurityProfileUpdate
) -> TenantSecurityProfile:
    """Milestone 13: `TenantSecurityProfile` has existed since Milestone 1
    with `repository.get_security_profile` reachable but never called by
    any route — these toggles were pure dead weight. This is the first
    write path. Note: `require_step_up_for_disruptive_actions` is now
    stored and readable, but `approve_action_run` doesn't yet read it back
    (see Milestone 13's Known Limitations) — it always enforces step-up
    for MFA-enabled users regardless of this toggle's value."""
    profile = await get_security_profile(session, tenant_id)
    if profile is None:
        raise NotFoundError("Tenant security profile not found.")
    if payload.require_mfa_for_admins is not None:
        profile.require_mfa_for_admins = payload.require_mfa_for_admins
    if payload.require_step_up_for_disruptive_actions is not None:
        profile.require_step_up_for_disruptive_actions = payload.require_step_up_for_disruptive_actions
    if payload.session_ttl_seconds is not None:
        profile.session_ttl_seconds = payload.session_ttl_seconds
    await session.flush()
    return profile


# Milestone 14: which tenant roles count as "admin" for
# `require_mfa_for_admins` purposes — a deliberate, documented judgment
# call (not derived from any formal specification), chosen as the two
# roles with the broadest sensitive-permission surface: `tenant_owner`
# holds every non-platform permission, and `security_administrator` holds
# `actions.approve_disruptive`, `users.manage`, and `trust_passport.manage`
# among others. Narrower admin-adjacent roles like `it_administrator`
# were deliberately left out.
ADMIN_ROLE_NAMES = frozenset({"tenant_owner", "security_administrator"})


async def is_mfa_enrollment_required(
    session: AsyncSession, *, tenant_id: uuid.UUID, role_name: str, user: User
) -> bool:
    """Milestone 14: `TenantSecurityProfile.require_mfa_for_admins` has
    existed since Milestone 1 with zero enforcement callers (Milestone
    13's own Known Limitations named this exact gap). This is the first
    real enforcement — called both by `core.deps.get_tenant_context` (the
    actual access-blocking gate) and by `/api/auth/me` (an informational
    flag so the frontend can redirect proactively instead of only
    discovering the block from a failed tenant API call)."""
    if role_name not in ADMIN_ROLE_NAMES or user.mfa_enabled:
        return False
    await set_tenant_context(session, tenant_id)
    profile = await get_security_profile(session, tenant_id)
    return profile is not None and profile.require_mfa_for_admins
