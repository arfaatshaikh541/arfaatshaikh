import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import set_rls_context
from app.core.email import (
    send_portal_invitation_email,
    send_portal_password_reset_email,
)
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError, ValidationFailedError
from app.core.security import generate_opaque_token, hash_password, hash_token, verify_password
from app.modules.audit.service import log_event
from app.modules.portal.models import PortalAccount, PortalInvitation
from app.modules.portal.models import PortalSession as PortalSessionModel
from app.modules.portal.repository import (
    PortalAccountRepository,
    PortalInvitationRepository,
    PortalPasswordResetTokenRepository,
    PortalSessionRepository,
)
from app.modules.tenancy.models import Tenant

settings = get_settings()

PORTAL_PASSWORD_RESET_TTL = timedelta(hours=1)
PORTAL_INVITATION_TTL = timedelta(days=7)


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Invitations
# ---------------------------------------------------------------------------

def invite_to_portal(db: Session, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, invited_by: uuid.UUID, tenant: Tenant) -> PortalInvitation:
    from app.modules.leads.repository import LeadRepository

    lead = LeadRepository(db).get(tenant_id, lead_id)
    if lead is None:
        raise NotFoundError("Lead not found.")
    if not lead.email:
        raise ValidationFailedError("This lead has no email address on file.", code="lead_missing_email")

    if PortalAccountRepository(db).get_by_lead(tenant_id, lead_id) is not None:
        raise ConflictError("This lead already has portal access.", code="already_has_portal_access")

    raw_token = generate_opaque_token()
    invitation = PortalInvitationRepository(db).create(
        tenant_id=tenant_id, lead_id=lead_id, email=lead.email.lower(), token_hash=hash_token(raw_token),
        invited_by=invited_by, expires_at=_utcnow() + PORTAL_INVITATION_TTL,
    )
    log_event(
        db, tenant_id=tenant_id, actor_user_id=invited_by, action="portal_invitation.created",
        entity_type="portal_invitation", entity_id=invitation.id, after={"lead_id": str(lead_id), "email": lead.email},
    )
    invite_url = f"{settings.api_base_url}/portal/{tenant.slug}/accept-invitation?token={raw_token}"
    send_portal_invitation_email(to=lead.email, tenant_name=tenant.name, invite_url=invite_url)
    return invitation


def accept_portal_invitation(db: Session, *, token: str, password: str) -> tuple[PortalAccount, PortalInvitation]:
    invitation_repo = PortalInvitationRepository(db)
    invitation = invitation_repo.get_by_token_hash(hash_token(token))
    if invitation is None:
        raise NotFoundError("Invitation not found or already used.")
    if invitation.accepted_at is not None or invitation.revoked_at is not None:
        raise ConflictError("This invitation has already been used or revoked.", code="invitation_invalid")
    if invitation.expires_at < _utcnow():
        raise ConflictError("This invitation has expired.", code="invitation_expired")

    # The invitation's token is the authorization proof for this specific
    # tenant — establish that as the RLS context before touching
    # `portal_accounts`, the same reasoning `identity_service.accept_invitation`
    # already uses for staff invitations.
    set_rls_context(db, tenant_id=invitation.tenant_id, is_platform_admin=False)

    account_repo = PortalAccountRepository(db)
    if account_repo.get_by_lead(invitation.tenant_id, invitation.lead_id) is not None:
        raise ConflictError("This lead already has portal access.", code="already_has_portal_access")

    account = account_repo.create(
        tenant_id=invitation.tenant_id, lead_id=invitation.lead_id, email=invitation.email, password_hash=hash_password(password)
    )
    invitation.accepted_at = _utcnow()

    log_event(
        db, tenant_id=invitation.tenant_id, actor_user_id=None, action="portal_invitation.accepted",
        entity_type="portal_invitation", entity_id=invitation.id,
    )
    return account, invitation


def revoke_portal_account(db: Session, *, tenant_id: uuid.UUID, account: PortalAccount, actor_id: uuid.UUID | None) -> PortalAccount:
    account.is_active = False
    db.add(account)
    db.flush()
    revoke_all_portal_sessions_for_account(db, account.id)
    log_event(db, tenant_id=tenant_id, actor_user_id=actor_id, action="portal_account.revoked", entity_type="portal_account", entity_id=account.id)
    return account


def list_portal_accounts(db: Session, tenant_id: uuid.UUID) -> list[PortalAccount]:
    return PortalAccountRepository(db).list_for_tenant(tenant_id)


# ---------------------------------------------------------------------------
# Login / logout / sessions
# ---------------------------------------------------------------------------

def authenticate_portal(db: Session, *, tenant_slug: str, email: str, password: str, ip_address: str) -> tuple[PortalAccount, Tenant]:
    """Verifies credentials for the client portal. Always raises the same
    generic error on any failure (unknown tenant slug, unknown email,
    wrong password, inactive account) so responses do not leak which case
    occurred — the same convention `identity_service.authenticate` uses."""
    from app.modules.tenancy import service as tenancy_service

    generic_error = UnauthorizedError("Invalid email or password.", code="invalid_credentials")

    tenant = tenancy_service.get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise generic_error

    account = PortalAccountRepository(db).get_by_email(tenant.id, email.lower())
    if account is None or not account.is_active:
        raise generic_error
    if not verify_password(password, account.password_hash):
        raise generic_error

    return account, tenant


def create_portal_session(
    db: Session, *, account: PortalAccount, ip_address: str | None, user_agent: str | None
) -> tuple[PortalSessionModel, str]:
    raw_token = generate_opaque_token()
    session = PortalSessionRepository(db).create(
        tenant_id=account.tenant_id, portal_account_id=account.id, session_token_hash=hash_token(raw_token),
        ip_address=ip_address, user_agent=user_agent,
        expires_at=_utcnow() + timedelta(hours=settings.portal_session_absolute_ttl_hours),
    )
    log_event(db, tenant_id=account.tenant_id, actor_user_id=None, action="portal_session.created", entity_type="portal_session", entity_id=session.id)
    return session, raw_token


def get_portal_session_by_raw_token(db: Session, raw_token: str) -> PortalSessionModel | None:
    session = PortalSessionRepository(db).get_by_token_hash(hash_token(raw_token))
    if session is None:
        return None
    if session.revoked_at is not None:
        return None
    if session.expires_at < _utcnow():
        return None
    idle_deadline = session.last_seen_at + timedelta(minutes=settings.portal_session_idle_ttl_minutes)
    if idle_deadline < _utcnow():
        return None
    return session


def touch_portal_session(db: Session, session: PortalSessionModel) -> None:
    session.last_seen_at = _utcnow()


def revoke_portal_session(db: Session, session: PortalSessionModel) -> None:
    PortalSessionRepository(db).revoke(session, revoked_at=_utcnow())


def revoke_all_portal_sessions_for_account(db: Session, portal_account_id: uuid.UUID) -> None:
    PortalSessionRepository(db).revoke_all_for_account(portal_account_id, revoked_at=_utcnow())


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------

def request_portal_password_reset(db: Session, *, tenant: Tenant, email: str) -> None:
    """Always returns silently regardless of whether the email exists, to
    avoid account enumeration. Only sends an email when a matching, active
    account is found."""
    account = PortalAccountRepository(db).get_by_email(tenant.id, email.lower())
    if account is None or not account.is_active:
        return
    raw_token = generate_opaque_token()
    PortalPasswordResetTokenRepository(db).create(
        tenant_id=tenant.id, portal_account_id=account.id, token_hash=hash_token(raw_token), expires_at=_utcnow() + PORTAL_PASSWORD_RESET_TTL
    )
    reset_url = f"{settings.api_base_url}/portal/{tenant.slug}/reset-password?token={raw_token}"
    send_portal_password_reset_email(to=account.email, tenant_name=tenant.name, reset_url=reset_url)


def reset_portal_password(db: Session, *, token: str, new_password: str) -> PortalAccount:
    token_repo = PortalPasswordResetTokenRepository(db)
    record = token_repo.get_by_token_hash(hash_token(token))
    if record is None or record.used_at is not None or record.expires_at < _utcnow():
        raise ConflictError("This password reset link is invalid or has expired.", code="reset_invalid")

    # The reset token's own `tenant_id` (denormalized — see the
    # `PortalPasswordResetToken` model docstring) lets us establish RLS
    # context before touching the (RLS-protected) `portal_accounts` row,
    # without needing to read that row first to discover its tenant.
    set_rls_context(db, tenant_id=record.tenant_id, is_platform_admin=False)
    account_repo = PortalAccountRepository(db)
    account = account_repo.get(record.tenant_id, record.portal_account_id)
    if account is None:
        raise NotFoundError("Account not found.")
    if not account.is_active:
        raise ForbiddenError("This account is no longer active.", code="account_inactive")

    account.password_hash = hash_password(new_password)
    record.used_at = _utcnow()
    revoke_all_portal_sessions_for_account(db, account.id)
    log_event(db, tenant_id=account.tenant_id, actor_user_id=None, action="portal_account.password_reset", entity_type="portal_account", entity_id=account.id)
    return account
