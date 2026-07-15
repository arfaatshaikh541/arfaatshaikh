from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.errors import (
    AuthenticationError,
    AuthorizationError,
    InvalidCredentialsError,
    NotFoundError,
)
from core.security import (
    generate_opaque_token,
    hash_password,
    hash_token,
    verify_password,
)
from db.session import set_user_context
from modules.identity.models import EmailVerificationToken, PasswordResetToken, Session, User
from modules.identity.schemas import MembershipSummary
from modules.permissions.models import Membership, Role
from modules.tenancy.models import Tenant

logger = structlog.get_logger("gridkeep.identity")

EMAIL_VERIFICATION_TTL = timedelta(hours=24)
PASSWORD_RESET_TTL = timedelta(hours=1)


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------- email --


async def issue_email_verification_token(session: AsyncSession, user: User) -> str:
    raw_token = generate_opaque_token()
    session.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=_now() + EMAIL_VERIFICATION_TTL,
        )
    )
    await session.flush()
    return raw_token


async def verify_email(session: AsyncSession, raw_token: str) -> User:
    token_hash = hash_token(raw_token)
    result = await session.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
    )
    token_row = result.scalar_one_or_none()
    if token_row is None or token_row.used_at is not None or token_row.expires_at <= _now():
        raise AuthenticationError("This verification link is invalid or has expired.")

    user_result = await session.execute(select(User).where(User.id == token_row.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise NotFoundError("Account not found.")

    user.email_verified = True
    user.email_verified_at = _now()
    token_row.used_at = _now()
    await session.flush()
    return user


# ---------------------------------------------------------------- auth --


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User:
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    # Always run the hasher even on a missing account, so response timing
    # doesn't disclose whether an email address is registered.
    dummy_hash = (
        "$argon2id$v=19$m=65536,t=3,p=2$AAAAAAAAAAAAAAAAAAAAAA$"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    )
    if user is None:
        verify_password(password, dummy_hash)
        raise InvalidCredentialsError("Incorrect email or password.")

    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Incorrect email or password.")

    if not user.is_active:
        raise AuthorizationError("This account has been deactivated.")

    if not user.email_verified:
        raise AuthenticationError("Please verify your email address before signing in.")

    return user


async def create_session(
    session: AsyncSession,
    user: User,
    *,
    active_membership_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, Session]:
    raw_token = generate_opaque_token()
    session_row = Session(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        active_membership_id=active_membership_id,
        expires_at=_now() + timedelta(seconds=settings.session_ttl_seconds),
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent else None,
        last_seen_at=_now(),
    )
    session.add(session_row)
    user.last_login_at = _now()
    await session.flush()
    return raw_token, session_row


async def revoke_session_by_token(session: AsyncSession, raw_token: str) -> None:
    token_hash = hash_token(raw_token)
    result = await session.execute(select(Session).where(Session.token_hash == token_hash))
    session_row = result.scalar_one_or_none()
    if session_row is not None and session_row.revoked_at is None:
        session_row.revoked_at = _now()
        await session.flush()


async def revoke_all_sessions_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    result = await session.execute(
        select(Session).where(Session.user_id == user_id, Session.revoked_at.is_(None))
    )
    for session_row in result.scalars().all():
        session_row.revoked_at = _now()
    await session.flush()


# ---------------------------------------------------------------- memberships --


async def list_memberships_for_user(session: AsyncSession, user_id: uuid.UUID) -> list[MembershipSummary]:
    """Lists every tenant the authenticated user belongs to. Relies on the
    `memberships` RLS policy's `user_id = app.current_user_id` clause —
    set here, scoped to this call, so the read never depends on a tenant
    already being selected (architecture §6)."""
    await set_user_context(session, user_id)
    result = await session.execute(
        select(Membership, Tenant, Role)
        .join(Tenant, Tenant.id == Membership.tenant_id)
        .join(Role, Role.id == Membership.role_id)
        .where(Membership.user_id == user_id, Membership.status == "active")
    )
    return [
        MembershipSummary(
            membership_id=membership.id,
            tenant_id=tenant.id,
            tenant_name=tenant.name,
            tenant_slug=tenant.slug,
            tenant_status=tenant.status,
            role_name=role.name,
        )
        for membership, tenant, role in result.all()
    ]


async def switch_active_tenant(
    session: AsyncSession, *, user_id: uuid.UUID, session_row: Session, membership_id: uuid.UUID
) -> Membership:
    """Re-validates the membership server-side before switching — the
    client can only ever select among the authenticated user's OWN active
    memberships, never an arbitrary tenant id (Rule 19)."""
    await set_user_context(session, user_id)
    result = await session.execute(
        select(Membership).where(
            Membership.id == membership_id,
            Membership.user_id == user_id,
            Membership.status == "active",
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise AuthorizationError("You don't have access to that workspace.")

    session_row.active_membership_id = membership.id
    await session.flush()
    return membership


# ---------------------------------------------------------------- password reset --


async def issue_password_reset_token(session: AsyncSession, user: User) -> str:
    raw_token = generate_opaque_token()
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=_now() + PASSWORD_RESET_TTL,
        )
    )
    await session.flush()
    return raw_token


async def reset_password(session: AsyncSession, raw_token: str, new_password: str) -> User:
    token_hash = hash_token(raw_token)
    result = await session.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    token_row = result.scalar_one_or_none()
    if token_row is None or token_row.used_at is not None or token_row.expires_at <= _now():
        raise AuthenticationError("This password reset link is invalid or has expired.")

    user_result = await session.execute(select(User).where(User.id == token_row.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise NotFoundError("Account not found.")

    user.password_hash = hash_password(new_password)
    token_row.used_at = _now()
    await revoke_all_sessions_for_user(session, user.id)
    await session.flush()
    return user
