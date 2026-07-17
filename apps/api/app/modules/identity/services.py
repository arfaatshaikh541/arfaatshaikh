"""Identity domain services: registration, email verification, login,
logout, and password reset.

Security properties enforced here:
  - Argon2id password hashing (never plaintext, never reversible).
  - Opaque, single-use, hashed, expiring tokens for verification/reset -
    the raw token exists only in the outbound email and this request's
    memory, never persisted or logged.
  - Password reset revokes every existing session for the account.
  - Login failures increment a counter and lock the account after a
    threshold, independent of the Redis-backed IP rate limit applied in
    the route layer.
  - Email enumeration is not possible via the password-reset-request
    endpoint: the response is identical whether or not the email exists.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    InvalidCredentialsError,
    ResourceNotFoundError,
)
from app.core.mail import send_email
from app.core.security import (
    generate_opaque_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.modules.identity import repositories as repo
from app.modules.identity.models import Session, User
from app.modules.tenancy.services import list_my_memberships

MAX_FAILED_LOGIN_ATTEMPTS = 10
ACCOUNT_LOCK_MINUTES = 15


async def register_user(
    session: AsyncSession, *, email: str, password: str, full_name: str
) -> User:
    existing = await repo.get_user_by_email(session, email)
    if existing is not None:
        raise ConflictError("An account with this email already exists.")

    password_hash = hash_password(password)
    user = await repo.create_user(
        session, email=email, password_hash=password_hash, full_name=full_name
    )

    settings = get_settings()
    raw_token = generate_opaque_token()
    expires_at = datetime.now(UTC) + timedelta(hours=settings.email_verification_token_ttl_hours)
    await repo.create_email_verification_token(
        session, user_id=user.id, token_hash=hash_token(raw_token), expires_at=expires_at
    )

    verify_url = f"{settings.api_base_url}/auth/verify-email?token={raw_token}"
    await send_email(
        to_email=user.email,
        subject="Verify your GRIDKEEP account",
        text_body=f"Welcome to GRIDKEEP. Verify your email by visiting: {verify_url}",
        html_body=f'<p>Welcome to GRIDKEEP.</p><p><a href="{verify_url}">Verify your email</a></p>',
    )
    return user


async def verify_email(session: AsyncSession, *, raw_token: str) -> User:
    token_row = await repo.get_valid_email_verification_token(session, hash_token(raw_token))
    now = datetime.now(UTC)
    if token_row is None or token_row.consumed_at is not None or token_row.expires_at < now:
        raise ResourceNotFoundError("This verification link is invalid or has expired.")

    user = await repo.get_user_by_id(session, token_row.user_id)
    if user is None:
        raise ResourceNotFoundError("This verification link is invalid or has expired.")

    user.email_verified = True
    token_row.consumed_at = now
    return user


async def login(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[User, Session, str]:
    """Returns (user, session_row, raw_session_token)."""
    settings = get_settings()
    now = datetime.now(UTC)

    user = await repo.get_user_by_email(session, email)
    if user is None:
        # Constant-shape failure: don't reveal whether the account exists.
        raise InvalidCredentialsError("Invalid email or password.")

    if user.locked_until is not None and user.locked_until > now:
        raise InvalidCredentialsError(
            "Account temporarily locked due to repeated failed login attempts."
        )

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=ACCOUNT_LOCK_MINUTES)
            user.failed_login_attempts = 0
        raise InvalidCredentialsError("Invalid email or password.")

    if not user.is_active:
        raise AuthenticationError("This account is deactivated.")

    user.failed_login_attempts = 0
    user.locked_until = None

    active_tenant_id: uuid.UUID | None = None
    memberships = await list_my_memberships(session, user.id)
    if len(memberships) == 1:
        active_tenant_id = memberships[0].tenant_id

    raw_token = generate_opaque_token()
    expires_at = now + timedelta(hours=settings.session_ttl_hours)
    session_row = await repo.create_session(
        session,
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=expires_at,
        active_tenant_id=active_tenant_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return user, session_row, raw_token


async def logout(session: AsyncSession, *, session_row: Session) -> None:
    session_row.revoked_at = datetime.now(UTC)


async def request_password_reset(session: AsyncSession, *, email: str) -> None:
    settings = get_settings()
    user = await repo.get_user_by_email(session, email)
    if user is None:
        return  # Do not reveal account existence.

    raw_token = generate_opaque_token()
    expires_at = datetime.now(UTC) + timedelta(hours=settings.password_reset_token_ttl_hours)
    await repo.create_password_reset_token(
        session, user_id=user.id, token_hash=hash_token(raw_token), expires_at=expires_at
    )
    reset_url = f"{settings.api_base_url}/auth/password-reset/confirm?token={raw_token}"
    await send_email(
        to_email=user.email,
        subject="Reset your GRIDKEEP password",
        text_body=f"Reset your password by visiting: {reset_url}",
        html_body=f'<p><a href="{reset_url}">Reset your password</a></p>',
    )


async def confirm_password_reset(
    session: AsyncSession, *, raw_token: str, new_password: str
) -> User:
    token_row = await repo.get_valid_password_reset_token(session, hash_token(raw_token))
    now = datetime.now(UTC)
    if token_row is None or token_row.consumed_at is not None or token_row.expires_at < now:
        raise ResourceNotFoundError("This password reset link is invalid or has expired.")

    user = await repo.get_user_by_id(session, token_row.user_id)
    if user is None:
        raise ResourceNotFoundError("This password reset link is invalid or has expired.")

    user.password_hash = hash_password(new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    token_row.consumed_at = now
    await repo.revoke_all_sessions_for_user(session, user.id, now=now)
    return user
