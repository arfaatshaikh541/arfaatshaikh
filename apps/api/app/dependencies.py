"""Shared FastAPI dependencies implementing the full authorization chain:

    session -> user -> tenant membership -> tenant status -> role
    permission -> (entitlement, where applicable)

No dependency in this chain ever trusts a tenant_id, role, or permission
supplied by the client. Tenant context is derived exclusively from the
server-side Session row's `active_tenant_id`, which is only ever changed
by the tenant-switch endpoint after re-verifying membership.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db, set_tenant_context
from app.core.exceptions import (
    AuthenticationError,
    CSRFValidationError,
    PermissionDeniedError,
    SessionExpiredError,
    TenantAccessDeniedError,
    TenantStatusError,
)
from app.core.security import hash_token
from app.modules.identity.models import Session as SessionModel
from app.modules.identity.models import User
from app.modules.permissions.models import PlatformRoleAssignment
from app.modules.permissions.repositories import get_permission_keys_for_role
from app.modules.tenancy.models import Membership, Tenant


@dataclass
class TenantContext:
    tenant_id: uuid.UUID
    tenant_status: str
    user_id: uuid.UUID
    membership_id: uuid.UUID
    role_id: uuid.UUID
    permissions: set[str]


async def get_current_session(request: Request, db: AsyncSession = Depends(get_db)) -> SessionModel:
    settings = get_settings()
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise AuthenticationError("Authentication required.")

    token_hash = hash_token(raw_token)
    stmt = select(SessionModel).where(SessionModel.token_hash == token_hash)
    result = await db.execute(stmt)
    session_row = result.scalar_one_or_none()
    if session_row is None:
        raise AuthenticationError("Authentication required.")
    if session_row.revoked_at is not None:
        raise SessionExpiredError("Session has been revoked.")
    if session_row.expires_at < datetime.now(UTC):
        raise SessionExpiredError("Session has expired.")
    return session_row


async def get_current_user(
    session_row: SessionModel = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> User:
    stmt = select(User).where(User.id == session_row.user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthenticationError("Account is not active.")
    return user


def verify_csrf(request: Request) -> None:
    """Double-submit CSRF check for cookie-authenticated mutating requests."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    settings = get_settings()
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    header_token = request.headers.get("x-csrf-token")
    if not cookie_token or not header_token or cookie_token != header_token:
        raise CSRFValidationError("CSRF validation failed.")


async def get_tenant_context(
    request: Request,
    session_row: SessionModel = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(verify_csrf),
) -> TenantContext:
    if session_row.active_tenant_id is None:
        raise TenantAccessDeniedError("No active tenant selected for this session.")

    tenant_id = session_row.active_tenant_id

    # Must happen before any query against a tenant-owned (RLS-protected)
    # table, including the membership lookup below - otherwise the GUC is
    # still unset (or stale from a previously pooled connection) and RLS
    # denies the very membership row that would prove access is legitimate.
    await set_tenant_context(db, tenant_id)

    tenant_stmt = select(Tenant).where(Tenant.id == tenant_id)
    tenant = (await db.execute(tenant_stmt)).scalar_one_or_none()
    if tenant is None:
        raise TenantAccessDeniedError("Tenant not found.")

    membership_stmt = select(Membership).where(
        Membership.tenant_id == tenant_id,
        Membership.user_id == user.id,
        Membership.status == "active",
    )
    membership = (await db.execute(membership_stmt)).scalar_one_or_none()
    if membership is None:
        raise TenantAccessDeniedError("You are not an active member of this tenant.")

    if tenant.status == "archived":
        raise TenantStatusError("This tenant has been archived.")
    if tenant.status == "suspended":
        raise TenantStatusError("This tenant is suspended.")

    permission_keys = await get_permission_keys_for_role(db, membership.role_id)

    return TenantContext(
        tenant_id=tenant_id,
        tenant_status=tenant.status,
        user_id=user.id,
        membership_id=membership.id,
        role_id=membership.role_id,
        permissions=permission_keys,
    )


READ_ONLY_TENANT_STATUSES = {"read_only"}


def require_permission(permission_key: str, allow_read_only: bool = False):
    """FastAPI dependency factory: verifies the caller's tenant membership
    grants `permission_key`, and that the tenant's status permits the
    action (a `read_only` tenant blocks all but explicitly allowed
    read-only-safe operations)."""

    async def _dependency(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if permission_key not in ctx.permissions:
            raise PermissionDeniedError(f"Missing required permission: {permission_key}")
        is_mutating_permission = not permission_key.endswith(".view")
        if (
            ctx.tenant_status in READ_ONLY_TENANT_STATUSES
            and is_mutating_permission
            and not allow_read_only
        ):
            raise TenantStatusError("This tenant is in read-only mode.")
        return ctx

    return _dependency


def require_platform_permission(permission_key: str):
    """FastAPI dependency factory for platform-role-gated endpoints. These
    do not go through tenant context - platform roles have tenant_id NULL
    and are checked against the caller's platform memberships."""

    async def _dependency(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if not user.is_platform_user:
            raise PermissionDeniedError("Platform access required.")

        assignment_stmt = select(PlatformRoleAssignment).where(
            PlatformRoleAssignment.user_id == user.id
        )
        assignments = (await db.execute(assignment_stmt)).scalars().all()
        for assignment in assignments:
            keys = await get_permission_keys_for_role(db, assignment.role_id)
            if permission_key in keys:
                return user
        raise PermissionDeniedError(f"Missing required platform permission: {permission_key}")

    return _dependency
