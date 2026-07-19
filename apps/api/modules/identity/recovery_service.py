from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationAppError,
)
from core.security import hash_token
from modules.identity.models import (
    AccountRecoveryRequest,
    MfaBackupCode,
    MfaChallengeToken,
    User,
)
from modules.permissions.models import Membership

REASON_MAX_LEN = 500


def _now() -> datetime:
    return datetime.now(UTC)


async def request_recovery(
    session: AsyncSession, *, mfa_challenge_token: str, reason: str
) -> AccountRecoveryRequest:
    """Only reachable with a valid, unexpired MFA challenge token — proof
    the requester passed the password check for this account, even though
    they cannot complete the second factor. Deliberately NOT an
    authenticated (session-based) action: by definition, a user who needs
    this has no session and cannot get one without it.

    Idempotent: re-submitting while a request is already pending returns
    the existing row rather than creating a second one — both because a
    genuinely locked-out user may retry the form, and because the unique
    partial index the migration adds (`ux_account_recovery_requests_one_
    pending_per_user`) would reject a second INSERT anyway. Checking first
    avoids surfacing a raw integrity-constraint error for an entirely
    ordinary retry."""
    token_hash = hash_token(mfa_challenge_token)
    token_row = (
        await session.execute(select(MfaChallengeToken).where(MfaChallengeToken.token_hash == token_hash))
    ).scalar_one_or_none()
    if token_row is None or token_row.used_at is not None or token_row.expires_at <= _now():
        raise AuthenticationError("This sign-in attempt has expired. Please sign in again.")

    user = (await session.execute(select(User).where(User.id == token_row.user_id))).scalar_one_or_none()
    if user is None or not user.mfa_enabled:
        raise AuthenticationError("This sign-in attempt is no longer valid. Please sign in again.")

    existing = (
        await session.execute(
            select(AccountRecoveryRequest).where(
                AccountRecoveryRequest.user_id == user.id,
                AccountRecoveryRequest.status == "pending",
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    request = AccountRecoveryRequest(
        user_id=user.id, reason=reason.strip()[:REASON_MAX_LEN], status="pending"
    )
    session.add(request)
    await session.flush()
    return request


async def list_pending_requests_for_tenant(
    session: AsyncSession, *, tenant_id: uuid.UUID
) -> list[tuple[AccountRecoveryRequest, User]]:
    """Visible only for requests from a user who holds an ACTIVE membership
    in this admin's own tenant — computed by joining at query time, since
    `AccountRecoveryRequest` deliberately isn't scoped to a single tenant
    (see its own docstring)."""
    result = await session.execute(
        select(AccountRecoveryRequest, User)
        .join(User, User.id == AccountRecoveryRequest.user_id)
        .join(Membership, Membership.user_id == User.id)
        .where(
            Membership.tenant_id == tenant_id,
            Membership.status == "active",
            AccountRecoveryRequest.status == "pending",
        )
        .distinct()
        .order_by(AccountRecoveryRequest.created_at.desc())
    )
    return list(result.all())


async def _get_visible_request_or_404(
    session: AsyncSession, *, request_id: uuid.UUID, tenant_id: uuid.UUID
) -> AccountRecoveryRequest:
    """The same tenant-membership join `list_pending_requests_for_tenant`
    uses, applied to a single row — an admin can only ever act on a
    request from a user who is an active member of *their* tenant, not by
    guessing a UUID for a request from an unrelated tenant's user."""
    result = await session.execute(
        select(AccountRecoveryRequest)
        .join(Membership, Membership.user_id == AccountRecoveryRequest.user_id)
        .where(
            AccountRecoveryRequest.id == request_id,
            Membership.tenant_id == tenant_id,
            Membership.status == "active",
        )
        .distinct()
    )
    request = result.scalar_one_or_none()
    if request is None:
        raise NotFoundError("Account recovery request not found.")
    return request


async def approve_recovery_request(
    session: AsyncSession, *, request_id: uuid.UUID, approver_user_id: uuid.UUID, tenant_id: uuid.UUID
) -> AccountRecoveryRequest:
    """Approval disables MFA for the target user — the same effect as the
    self-service `disable_mfa`, just reached via a different, vouching
    human instead of a TOTP code the requester no longer has. It does NOT
    mint a session: the user still has to log in fresh through the normal
    `/api/auth/login` path, which will now succeed without an MFA
    challenge, and can re-enroll MFA immediately afterward.

    `request.user_id == approver_user_id` is checked unconditionally —
    not "not the same session", but "not the same account", full stop.
    A user who still holds a separate, still-valid session elsewhere
    cannot use it to approve their own recovery and strip their own MFA
    without ever proving they lost their second factor; that would turn
    this recovery path into a bypass for anyone holding any valid session
    at all."""
    request = await _get_visible_request_or_404(session, request_id=request_id, tenant_id=tenant_id)
    if request.status != "pending":
        raise ConflictError(f"This recovery request is '{request.status}', not pending.")
    if request.user_id == approver_user_id:
        raise ValidationAppError("You cannot approve your own account-recovery request.")

    target_user = (await session.execute(select(User).where(User.id == request.user_id))).scalar_one()
    target_user.mfa_enabled = False
    target_user.mfa_totp_secret_encrypted = None
    await session.execute(delete(MfaBackupCode).where(MfaBackupCode.user_id == target_user.id))
    await session.execute(
        delete(MfaChallengeToken).where(
            MfaChallengeToken.user_id == target_user.id, MfaChallengeToken.used_at.is_(None)
        )
    )

    request.status = "approved"
    request.resolved_by_user_id = approver_user_id
    request.resolved_at = _now()
    request.resolved_in_tenant_id = tenant_id
    await session.flush()
    return request


async def deny_recovery_request(
    session: AsyncSession, *, request_id: uuid.UUID, approver_user_id: uuid.UUID, tenant_id: uuid.UUID
) -> AccountRecoveryRequest:
    request = await _get_visible_request_or_404(session, request_id=request_id, tenant_id=tenant_id)
    if request.status != "pending":
        raise ConflictError(f"This recovery request is '{request.status}', not pending.")
    if request.user_id == approver_user_id:
        raise ValidationAppError("You cannot deny your own account-recovery request.")

    request.status = "denied"
    request.resolved_by_user_id = approver_user_id
    request.resolved_at = _now()
    request.resolved_in_tenant_id = tenant_id
    await session.flush()
    return request
