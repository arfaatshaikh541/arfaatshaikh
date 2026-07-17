from __future__ import annotations

import base64
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import pyotp
import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.errors import (
    AuthenticationError,
    AuthorizationError,
    InvalidCredentialsError,
    NotFoundError,
    ValidationAppError,
)
from core.security import (
    generate_opaque_token,
    hash_password,
    hash_token,
    verify_password,
)
from db.session import set_user_context
from modules.credential_vault.adapters.base import EncryptedSecret
from modules.credential_vault.service import get_vault_adapter
from modules.identity.models import (
    EmailVerificationToken,
    MfaBackupCode,
    MfaChallengeToken,
    PasswordResetToken,
    Session,
    User,
)
from modules.identity.schemas import MembershipSummary
from modules.permissions.models import Membership, Role
from modules.tenancy.models import Tenant

logger = structlog.get_logger("gridkeep.identity")

EMAIL_VERIFICATION_TTL = timedelta(hours=24)
PASSWORD_RESET_TTL = timedelta(hours=1)
MFA_CHALLENGE_TOKEN_TTL = timedelta(minutes=10)
STEP_UP_TTL_SECONDS = 300
MFA_TOTP_ISSUER = "GRIDKEEP"


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


async def get_platform_role_name(session: AsyncSession, user: User) -> str | None:
    """`User.platform_role_id` is a bare FK, not an ORM relationship (kept
    structurally separate from tenant roles per Rule: platform roles
    remain separated), so the name has to be resolved with its own query
    rather than a plain attribute read."""
    if not user.is_platform_user or user.platform_role_id is None:
        return None
    role = (await session.execute(select(Role).where(Role.id == user.platform_role_id))).scalar_one_or_none()
    return role.name if role else None


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


# ---------------------------------------------------------------- mfa --
#
# `User.mfa_totp_secret_encrypted`/`mfa_enabled` and
# `Session.mfa_verified`/`step_up_expires_at` have existed since Milestone
# 1 with `core.deps.require_step_up` already implemented and tested, but
# no route ever used any of it. This is what finally wires it up. The
# encrypted secret reuses `credential_vault`'s envelope-encryption
# VaultAdapter (Milestone 1) rather than inventing a second encryption
# primitive — `EncryptedSecret`'s four fields are packed into the single
# `String(500)` column the schema already defined, since a TOTP secret
# doesn't need its own multi-column table the way `IntegrationCredential`
# does.


def _pack_encrypted_secret(secret: EncryptedSecret) -> str:
    parts = (
        str(secret.key_version),
        base64.b64encode(secret.nonce).decode("ascii"),
        base64.b64encode(secret.wrapped_dek).decode("ascii"),
        base64.b64encode(secret.ciphertext).decode("ascii"),
    )
    return ":".join(parts)


def _unpack_encrypted_secret(packed: str) -> EncryptedSecret:
    key_version, nonce_b64, wrapped_dek_b64, ciphertext_b64 = packed.split(":")
    return EncryptedSecret(
        key_version=int(key_version),
        nonce=base64.b64decode(nonce_b64),
        wrapped_dek=base64.b64decode(wrapped_dek_b64),
        ciphertext=base64.b64decode(ciphertext_b64),
    )


def _decrypt_mfa_secret(user: User) -> str:
    packed = user.mfa_totp_secret_encrypted
    if packed is None:
        raise ValidationAppError("Multi-factor authentication is not set up for this account.")
    plaintext = get_vault_adapter().decrypt(_unpack_encrypted_secret(packed))
    return plaintext.decode("utf-8")


def verify_totp_code(totp_secret: str, code: str) -> bool:
    """`valid_window=1` accepts the previous and next 30-second window
    alongside the current one — the standard TOTP clock-skew tolerance,
    not a security weakening (each window is still only valid once
    correctly, and 30s either side is well within normal client/server
    drift)."""
    return pyotp.TOTP(totp_secret).verify(code, valid_window=1)


async def enroll_mfa(session: AsyncSession, user: User) -> tuple[str, str]:
    """Generates a new TOTP secret and stores it encrypted, but does NOT
    set `mfa_enabled` — enrollment isn't complete until `confirm_mfa_enrollment`
    proves the user's authenticator app actually has the secret (the same
    reasoning any TOTP enrollment flow uses: showing a secret proves
    nothing was received correctly)."""
    secret = pyotp.random_base32()
    encrypted = get_vault_adapter().encrypt(secret.encode("utf-8"))
    user.mfa_totp_secret_encrypted = _pack_encrypted_secret(encrypted)
    await session.flush()
    provisioning_uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=MFA_TOTP_ISSUER)
    return secret, provisioning_uri


BACKUP_CODE_COUNT = 10
# Excludes visually-ambiguous characters (0/O, 1/I/L) since these codes are
# meant to be handwritten or read off a screen during a real recovery.
_BACKUP_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _generate_backup_code() -> str:
    raw = "".join(secrets.choice(_BACKUP_CODE_ALPHABET) for _ in range(10))
    return f"{raw[:5]}-{raw[5:]}"


def _normalize_backup_code(code: str) -> str:
    return code.strip().upper()


async def _issue_backup_codes(session: AsyncSession, user: User) -> list[str]:
    """Milestone 24: invalidates any existing codes and issues a fresh
    batch of `BACKUP_CODE_COUNT` — called on enrollment confirm and on
    explicit regeneration. Returns the plaintext codes exactly once; only
    each code's SHA-256 hash is ever persisted, the same
    generate-hash-store-consume shape every other token in this module
    uses."""
    await session.execute(delete(MfaBackupCode).where(MfaBackupCode.user_id == user.id))
    plaintext_codes = [_generate_backup_code() for _ in range(BACKUP_CODE_COUNT)]
    for code in plaintext_codes:
        session.add(MfaBackupCode(user_id=user.id, code_hash=hash_token(code)))
    await session.flush()
    return plaintext_codes


async def _consume_backup_code(session: AsyncSession, user: User, backup_code: str) -> bool:
    """Returns True and marks the code used if it matches an unused
    backup code for this user, False otherwise. Input is
    case/whitespace-normalized since users retype these by hand."""
    code_hash = hash_token(_normalize_backup_code(backup_code))
    result = await session.execute(
        select(MfaBackupCode).where(
            MfaBackupCode.user_id == user.id,
            MfaBackupCode.code_hash == code_hash,
            MfaBackupCode.used_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return False
    row.used_at = _now()
    await session.flush()
    return True


async def confirm_mfa_enrollment(session: AsyncSession, user: User, code: str) -> list[str]:
    """Milestone 24: returns a fresh batch of backup codes now that
    enrollment succeeds — the caller (the `/mfa/confirm` route) must show
    these to the user exactly once, since only their hash is persisted."""
    secret = _decrypt_mfa_secret(user)
    if not verify_totp_code(secret, code):
        raise ValidationAppError("That code doesn't match. Please try again.")
    user.mfa_enabled = True
    await session.flush()
    return await _issue_backup_codes(session, user)


async def regenerate_backup_codes(session: AsyncSession, user: User, code: str) -> list[str]:
    """Milestone 24: requires a fresh TOTP code, the same trust level
    `disable_mfa` already requires — proves the caller still controls the
    authenticator, not just an active session. A user who has lost both
    the authenticator and every backup code has no self-service path here
    (documented as a Known Limitation); that's a deliberately narrower
    scope than a full account-recovery flow."""
    if not user.mfa_enabled:
        raise ValidationAppError("Multi-factor authentication is not enabled for this account.")
    secret = _decrypt_mfa_secret(user)
    if not verify_totp_code(secret, code):
        raise ValidationAppError("That code doesn't match. Please try again.")
    return await _issue_backup_codes(session, user)


async def disable_mfa(session: AsyncSession, user: User, code: str) -> None:
    if not user.mfa_enabled:
        raise ValidationAppError("Multi-factor authentication is not enabled for this account.")
    secret = _decrypt_mfa_secret(user)
    if not verify_totp_code(secret, code):
        raise ValidationAppError("That code doesn't match. Please try again.")
    user.mfa_enabled = False
    user.mfa_totp_secret_encrypted = None
    await session.execute(delete(MfaBackupCode).where(MfaBackupCode.user_id == user.id))
    await session.flush()


async def issue_mfa_challenge_token(session: AsyncSession, user: User) -> str:
    raw_token = generate_opaque_token()
    session.add(
        MfaChallengeToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=_now() + MFA_CHALLENGE_TOKEN_TTL,
        )
    )
    await session.flush()
    return raw_token


async def consume_mfa_challenge_token(
    session: AsyncSession, raw_token: str, *, code: str | None = None, backup_code: str | None = None
) -> User:
    """Milestone 24: accepts either a TOTP `code` or a `backup_code` (not
    both, but exactly one is required) — the login-challenge is the one
    place a backup code is actually usable, since it exists precisely for
    "I no longer have my authenticator device"."""
    if not code and not backup_code:
        raise InvalidCredentialsError("Incorrect verification code.")

    token_hash = hash_token(raw_token)
    result = await session.execute(
        select(MfaChallengeToken).where(MfaChallengeToken.token_hash == token_hash)
    )
    token_row = result.scalar_one_or_none()
    if token_row is None or token_row.used_at is not None or token_row.expires_at <= _now():
        raise AuthenticationError("This sign-in attempt has expired. Please sign in again.")

    user_result = await session.execute(select(User).where(User.id == token_row.user_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.mfa_enabled:
        raise AuthenticationError("This sign-in attempt is no longer valid. Please sign in again.")

    if code:
        secret = _decrypt_mfa_secret(user)
        verified = verify_totp_code(secret, code)
    else:
        verified = await _consume_backup_code(session, user, backup_code)
    if not verified:
        raise InvalidCredentialsError("Incorrect verification code.")

    token_row.used_at = _now()
    await session.flush()
    return user


async def step_up_session(
    session: AsyncSession, user: User, *, session_id: uuid.UUID, code: str
) -> Session:
    if not user.mfa_enabled:
        raise ValidationAppError(
            "Step-up verification requires multi-factor authentication to be enabled first."
        )
    secret = _decrypt_mfa_secret(user)
    if not verify_totp_code(secret, code):
        raise InvalidCredentialsError("Incorrect verification code.")

    result = await session.execute(select(Session).where(Session.id == session_id))
    session_row = result.scalar_one_or_none()
    if session_row is None:
        raise AuthenticationError("Your session is no longer valid. Please sign in again.")
    session_row.mfa_verified = True
    session_row.step_up_expires_at = _now() + timedelta(seconds=STEP_UP_TTL_SECONDS)
    await session.flush()
    return session_row
