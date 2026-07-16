from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import Cookie, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.config import settings
from core.errors import (
    AuthenticationError,
    AuthorizationError,
    TenantStatusError,
)
from core.security import constant_time_equals, hash_token
from db.session import get_db, platform_admin_scoped_session, set_user_context, tenant_scoped_session
from modules.entitlements.service import resolve_entitlements
from modules.identity.models import Session as SessionModel
from modules.identity.models import User
from modules.permissions.models import Membership, Role, RolePermission
from modules.tenancy.models import Tenant

WRITE_BLOCKED_STATUSES = {"suspended", "archived", "read_only"}


@dataclass(frozen=True)
class AuthContext:
    """Identity established purely from the session cookie — no tenant
    resolved yet. Used by tenant-switch and platform-only routes."""

    session_id: uuid.UUID
    user: User


@dataclass(frozen=True)
class TenantContext:
    """The single object every tenant-scoped route depends on. Built
    entirely from server-side state (session -> membership -> role) —
    never from a client-supplied tenant id or role claim (Rule 19)."""

    tenant_id: uuid.UUID
    tenant_status: str
    tenant_slug: str
    membership_id: uuid.UUID
    role_name: str
    permissions: frozenset[str] = field(default_factory=frozenset)
    user: User = None  # type: ignore[assignment]
    is_platform_admin: bool = False

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions


async def _get_session_token(
    gridkeep_session: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> str | None:
    return gridkeep_session


async def get_auth_context(
    token: str | None = Depends(_get_session_token),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    if not token:
        raise AuthenticationError("Sign in to continue.")

    token_hash = hash_token(token)
    result = await db.execute(
        select(SessionModel).where(SessionModel.token_hash == token_hash)
    )
    session_row = result.scalar_one_or_none()

    if session_row is None or session_row.revoked_at is not None:
        raise AuthenticationError("Your session is no longer valid. Please sign in again.")

    now = datetime.now(UTC)
    if session_row.expires_at <= now:
        raise AuthenticationError("Your session has expired. Please sign in again.")

    user_result = await db.execute(select(User).where(User.id == session_row.user_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthenticationError("This account is no longer active.")

    session_row.last_seen_at = now
    await db.commit()

    return AuthContext(session_id=session_row.id, user=user)


async def get_tenant_context(
    request: Request,
    token: str | None = Depends(_get_session_token),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """Resolves the active tenant purely from the session's
    `active_membership_id` — set via the tenant-switch endpoint, which
    itself re-validates membership server-side. The client cannot select an
    arbitrary tenant by sending a header or query parameter."""
    if not token:
        raise AuthenticationError("Sign in to continue.")

    token_hash = hash_token(token)
    result = await db.execute(
        select(SessionModel).where(SessionModel.token_hash == token_hash)
    )
    session_row = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if (
        session_row is None
        or session_row.revoked_at is not None
        or session_row.expires_at <= now
    ):
        raise AuthenticationError("Your session is no longer valid. Please sign in again.")

    if session_row.active_membership_id is None:
        raise AuthenticationError("Select a workspace to continue.")

    # `memberships` RLS only allows a row through when the tenant matches
    # OR the row belongs to the caller — we don't know the tenant yet
    # (that's what this query resolves), so establish the caller identity
    # first via the `app.current_user_id` session variable.
    await set_user_context(db, session_row.user_id)

    membership_result = await db.execute(
        select(Membership)
        .options(selectinload(Membership.role).selectinload(Role.permissions).selectinload(RolePermission.permission))
        .where(Membership.id == session_row.active_membership_id)
    )
    membership = membership_result.scalar_one_or_none()
    if membership is None or membership.status != "active":
        raise AuthenticationError("Your access to this workspace is no longer active.")

    user_result = await db.execute(select(User).where(User.id == session_row.user_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthenticationError("This account is no longer active.")

    tenant_result = await db.execute(select(Tenant).where(Tenant.id == membership.tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    if tenant is None:
        raise AuthenticationError("Workspace not found.")

    permissions = frozenset(rp.permission.key for rp in membership.role.permissions)

    return TenantContext(
        tenant_id=tenant.id,
        tenant_status=tenant.status,
        tenant_slug=tenant.slug,
        membership_id=membership.id,
        role_name=membership.role.name,
        permissions=permissions,
        user=user,
        is_platform_admin=False,
    )


async def get_tenant_db(
    ctx: TenantContext = Depends(get_tenant_context),
) -> AsyncGenerator[AsyncSession, None]:
    """Tenant-scoped DB session with Postgres RLS session variables set.
    This is the ONLY way tenant-facing route handlers should touch the
    database (see db/session.py + docs/architecture §6-7)."""
    async with tenant_scoped_session(ctx.tenant_id, is_platform_admin=ctx.is_platform_admin) as session:
        yield session


def require_permission(permission: str):
    """Dependency factory — step 4 of the authorization pipeline
    (docs/architecture §9). Composes with require_tenant_write for
    mutating routes."""

    async def _checker(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if not ctx.has_permission(permission):
            raise AuthorizationError(
                f"Your role does not have the '{permission}' permission.",
                details={"required_permission": permission},
            )
        return ctx

    return _checker


def require_tenant_write(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
    """Step 3 of the authorization pipeline — blocks mutations when the
    tenant is read_only, suspended or archived."""
    if ctx.tenant_status in WRITE_BLOCKED_STATUSES:
        raise TenantStatusError(
            f"This workspace is currently {ctx.tenant_status.replace('_', ' ')} and cannot be modified.",
            details={"tenant_status": ctx.tenant_status},
        )
    return ctx


def require_entitlement(module_key: str):
    """Dependency factory — step 5 of the authorization pipeline. Resolves
    entitlements fresh per request; never trusts a client-cached flag."""

    async def _checker(
        ctx: TenantContext = Depends(get_tenant_context),
        db: AsyncSession = Depends(get_tenant_db),
    ) -> TenantContext:
        entitlements = await resolve_entitlements(db, tenant_id=ctx.tenant_id)
        if module_key not in entitlements.entitled_modules:
            raise AuthorizationError(
                "This feature isn't included in your current plan.",
                details={"module": module_key, "upgrade_required": True},
            )
        return ctx

    return _checker


@dataclass(frozen=True)
class PlatformContext:
    """Structurally separate from TenantContext — a platform role's
    permissions are never merged with, or evaluated against, a tenant
    permission check (Rule: platform roles remain separated)."""

    user: User
    role_name: str
    permissions: frozenset[str]

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions


async def get_platform_context(
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> PlatformContext:
    if not auth.user.is_platform_user or auth.user.platform_role_id is None:
        raise AuthorizationError("Platform access is required for this operation.")

    role_result = await db.execute(
        select(Role)
        .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
        .where(Role.id == auth.user.platform_role_id, Role.is_platform_role.is_(True))
    )
    role = role_result.scalar_one_or_none()
    if role is None:
        raise AuthorizationError("Platform role not found.")

    permissions = frozenset(rp.permission.key for rp in role.permissions)
    return PlatformContext(user=auth.user, role_name=role.name, permissions=permissions)


def require_platform_permission(permission: str):
    async def _checker(ctx: PlatformContext = Depends(get_platform_context)) -> PlatformContext:
        if not ctx.has_permission(permission):
            raise AuthorizationError(
                f"Your platform role does not have the '{permission}' permission.",
                details={"required_permission": permission},
            )
        return ctx

    return _checker


async def get_platform_admin_db(
    _ctx: PlatformContext = Depends(get_platform_context),
) -> AsyncGenerator[AsyncSession, None]:
    """Cross-tenant-visible DB session for platform routes that read data
    spanning more than one tenant (e.g. the platform-wide audit log).
    Depends on `get_platform_context` only to confirm the caller IS a
    platform user at all — routes still separately apply
    `require_platform_permission` for the specific capability, exactly as
    `get_tenant_db` composes with `require_permission`."""
    async with platform_admin_scoped_session() as session:
        yield session


async def require_csrf(
    request: Request,
    csrf_cookie: str | None = Cookie(default=None, alias=settings.csrf_cookie_name),
    x_csrf_token: str | None = Header(default=None),
) -> None:
    """Double-submit CSRF check for cookie-authenticated mutating requests.
    Bearer-token (service/API-key) callers are exempt in practice because
    they never send the session cookie in the first place, so this
    dependency simply has nothing to compare against for them once that
    auth path is added in a later milestone."""
    if not csrf_cookie or not x_csrf_token or not constant_time_equals(csrf_cookie, x_csrf_token):
        raise AuthorizationError("Missing or invalid CSRF token.")


def require_step_up(max_age_seconds: int = 300):
    """Step-up auth gate for sensitive operations (credential vault access,
    role changes, disruptive-action approval — architecture §8). Wired to
    `actions.approve_action_run` in Milestone 13.

    Only enforced for users who have MFA enabled: `mfa_enabled` defaults
    to false and enrollment is self-service (Milestone 13), so requiring
    step-up unconditionally would lock every user who hasn't opted in out
    of disruptive-action approval entirely, with no way to ever satisfy
    the gate. A user without MFA gets the pre-Milestone-13 behaviour
    (permission check only); a user with MFA enabled must have recently
    re-proven it."""

    async def _checker(
        token: str | None = Depends(_get_session_token),
        db: AsyncSession = Depends(get_db),
    ) -> bool:
        if not token:
            raise AuthenticationError("Sign in to continue.")
        result = await db.execute(
            select(SessionModel, User)
            .join(User, User.id == SessionModel.user_id)
            .where(SessionModel.token_hash == hash_token(token))
        )
        row = result.first()
        if row is None:
            raise AuthenticationError("Sign in to continue.")
        session_row, user = row

        if not user.mfa_enabled:
            return True

        now = datetime.now(UTC)
        if session_row.step_up_expires_at is None or session_row.step_up_expires_at <= now:
            raise AuthorizationError(
                "Please re-confirm your identity to continue.",
                details={"step_up_required": True},
            )
        return True

    return _checker
