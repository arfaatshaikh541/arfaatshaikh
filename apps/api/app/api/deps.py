"""Shared FastAPI dependencies.

get_current_membership is the enforcement point for tenant isolation: it
re-derives tenant context from a verified database lookup on every
request rather than trusting any client-supplied claim on its own. See
docs/architecture/tenant-isolation-strategy.md.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.cookies import ACCESS_TOKEN_COOKIE, TENANT_HEADER
from app.core.security import decode_access_token
from app.db.base import utcnow
from app.db.session import get_db
from app.models.membership import Membership
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.membership import MembershipRepository
from app.repositories.session import SessionRepository
from app.repositories.tenant import TenantRepository
from app.repositories.user import UserRepository


def get_current_user(
    access_token: str | None = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    if access_token is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    try:
        payload = decode_access_token(access_token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Not authenticated.") from None

    try:
        user_id = uuid.UUID(payload["sub"])
        session_id = uuid.UUID(payload["sid"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Not authenticated.") from None

    # Access tokens intentionally carry no authorization claims, only
    # identity - the session row is re-checked on every request so that
    # logout / revoke-session / password-reset take effect immediately
    # rather than waiting for the short-lived JWT to expire on its own.
    # See docs/architecture/authentication-strategy.md.
    session = SessionRepository(db).get_by_id(session_id)
    if (
        session is None
        or session.user_id != user_id
        or session.revoked_at is not None
        or session.expires_at < utcnow()
    ):
        raise HTTPException(status_code=401, detail="Not authenticated.")

    user = UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return user


def get_optional_current_user(
    access_token: str | None = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE),
    db: Session = Depends(get_db),
) -> User | None:
    if access_token is None:
        return None
    try:
        return get_current_user(access_token=access_token, db=db)
    except HTTPException:
        return None


@dataclass
class MembershipContext:
    tenant: Tenant
    membership: Membership
    user: User
    permission_codes: frozenset[str] = field(default_factory=frozenset)

    @property
    def tenant_id(self) -> uuid.UUID:
        return self.tenant.id


def get_current_membership(
    x_tenant_id: str | None = Header(default=None, alias=TENANT_HEADER),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MembershipContext:
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header is required.")
    try:
        tenant_id = uuid.UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant id.") from None

    tenant = TenantRepository(db).get_by_id(tenant_id)
    if tenant is None:
        # 404, not 403: don't confirm/deny existence of a tenant to a non-member.
        raise HTTPException(status_code=404, detail="Tenant not found.")

    membership = MembershipRepository(db).get_for_user_and_tenant(user.id, tenant_id)
    if membership is None or membership.status != "active":
        raise HTTPException(status_code=403, detail="You are not a member of this tenant.")

    if tenant.status != "active":
        raise HTTPException(status_code=403, detail="This tenant account is not active.")

    permission_codes = frozenset(p.code for p in membership.role.permissions)
    return MembershipContext(
        tenant=tenant, membership=membership, user=user, permission_codes=permission_codes
    )


def require_permission(code: str):  # type: ignore[no-untyped-def]
    def dependency(ctx: MembershipContext = Depends(get_current_membership)) -> MembershipContext:
        if code not in ctx.permission_codes:
            raise HTTPException(status_code=403, detail=f"You do not have the '{code}' permission.")
        return ctx

    return dependency


def get_platform_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_platform_super_admin:
        raise HTTPException(status_code=403, detail="Platform administrator access required.")
    return user


def client_ip(request: Request, x_forwarded_for: str | None = Header(default=None)) -> str:
    # Only trust X-Forwarded-For when the deployment sits behind a known
    # reverse proxy that sets it (configured at the proxy, not here); local
    # dev and direct connections fall back to the socket peer address.
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
