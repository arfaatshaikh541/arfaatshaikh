from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.security_contracts import ACCOUNT_RECOVERY_STATUSES
from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A person. Not tenant-scoped — one person may hold memberships in
    multiple tenants (Rule: support user membership in multiple tenants)."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_platform_user: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    platform_role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="SET NULL"), nullable=True
    )
    mfa_totp_secret_encrypted: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sessions: Mapped[list[Session]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Session(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Server-side session record — see ADR-3. `token_hash` is the only
    persisted representation of the session token; the raw token is only
    ever held by the client cookie and this process's memory during issue/
    validate, never logged (see core.errors + structlog redaction)."""

    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    active_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mfa_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    step_up_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class PasswordResetToken(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmailVerificationToken(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "email_verification_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MfaBackupCode(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Milestone 24: single-use recovery codes for a user who has lost
    their authenticator device — the self-service recovery path MFA has
    lacked since Milestone 13. Same generate-hash-store-consume shape as
    every other token table in this module, but deliberately no
    `expires_at`: a backup code is meant to sit unused for months until
    the one day it's actually needed, unlike a password-reset or
    email-verification token."""

    __tablename__ = "mfa_backup_codes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MfaChallengeToken(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Milestone 13: a short-lived, single-use proof that a user already
    passed the password check, issued by `login()` in place of a real
    session when `User.mfa_enabled` is true — the same
    generate-hash-store-consume shape as `PasswordResetToken`/
    `EmailVerificationToken`, not a new pattern. Deliberately its own
    table rather than a flag on `Session`: the whole point is that no
    session exists yet until the TOTP code is also verified.

    Hardening-programme Milestone 2 (finding H-01): `failed_attempts` was
    added because a wrong guess previously left the token usable for the
    rest of its 10-minute TTL — no counter existed anywhere, so an
    attacker holding a valid token could try the entire 6-digit TOTP space
    with no server-side lockout. `consume_mfa_challenge_token` now
    increments this on every wrong guess and treats the token as invalid
    once it reaches `MFA_CHALLENGE_MAX_FAILED_ATTEMPTS`, independent of
    (and a durable backstop to) the Redis-backed per-token rate limit
    added alongside it in `modules.identity.routes`."""

    __tablename__ = "mfa_challenge_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_attempts: Mapped[int] = mapped_column(nullable=False, default=0)


class AccountRecoveryRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Hardening-programme Milestone 2: the self-service MFA-lockout
    recovery path Milestone 24's backup codes don't fully close — a user
    who has lost their authenticator device AND every backup code has no
    way back in without a human, different from themselves, vouching for
    their identity. Mirrors `platform_admin.models.SupportAccessGrant`'s
    second-approver shape rather than inventing a new approval pattern:
    created `pending`, resolved by a *different* user entirely (never the
    requester, on any session, ever — enforced in `recovery_service`, not
    just by convention), and every resolution is audited.

    Deliberately carries NO `tenant_id` column: `User` is explicitly
    documented as holding memberships across multiple tenants, and a
    locked-out user may belong to more than one. Visibility for a
    reviewing admin is computed at query time by joining to that admin's
    own tenant's memberships for the requesting user (see
    `recovery_service.list_pending_requests_for_tenant`) — the same
    reasoning `invitations` already uses for having no RLS policy of its
    own (see migration 762368bc730d)."""

    __tablename__ = "account_recovery_requests"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(*ACCOUNT_RECOVERY_STATUSES, name="account_recovery_status"), nullable=False, default="pending"
    )
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_in_tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True
    )
