import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import set_rls_context
from app.core.email import (
    send_invitation_email,
    send_password_reset_email,
    send_verification_email,
    send_welcome_set_password_email,
)
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import (
    generate_opaque_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.modules.audit.service import log_event
from app.modules.identity.models import Invitation, MembershipStatus, User
from app.modules.identity.models import Session as SessionModel
from app.modules.identity.repository import (
    InvitationRepository,
    LoginAttemptRepository,
    MembershipRepository,
    SessionRepository,
    TokenRepository,
    UserRepository,
)
from app.modules.permissions import service as permissions_service
from app.modules.tenancy import service as tenancy_service
from app.modules.tenancy.models import TenantStatus

settings = get_settings()

EMAIL_VERIFICATION_TTL = timedelta(hours=24)
PASSWORD_RESET_TTL = timedelta(hours=1)
INVITATION_TTL = timedelta(days=7)


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Platform-admin-driven account provisioning
# ---------------------------------------------------------------------------

def provision_tenant_owner(db: Session, *, email: str, first_name: str, last_name: str, tenant_name: str) -> User:
    """Creates the first (Owner) account for a newly created tenant.

    There is no existing tenant member to send a normal invitation, so
    the account is created directly with an unusable random password
    hash and a password-reset token is issued immediately, delivered via
    a "set your password" welcome email — the account cannot be logged
    into until that link is used.
    """
    user_repo = UserRepository(db)
    existing = user_repo.get_by_email(email.lower())
    if existing is not None:
        user = existing
    else:
        unusable_password = generate_opaque_token(num_bytes=48)
        user = user_repo.create(
            email=email.lower(), password_hash=hash_password(unusable_password),
            first_name=first_name, last_name=last_name,
        )

    raw_token = generate_opaque_token()
    TokenRepository(db).create_password_reset_token(
        user_id=user.id, token_hash=hash_token(raw_token), expires_at=_utcnow() + PASSWORD_RESET_TTL
    )
    set_password_url = f"{settings.api_base_url}/reset-password?token={raw_token}"
    send_welcome_set_password_email(to=user.email, tenant_name=tenant_name, set_password_url=set_password_url)
    return user


# ---------------------------------------------------------------------------
# Invitations & registration
# ---------------------------------------------------------------------------

def invite_user(
    db: Session, *, tenant_id: uuid.UUID, email: str, role_id: uuid.UUID, invited_by: uuid.UUID, tenant_name: str
) -> Invitation:
    role = permissions_service.get_role(db, role_id)
    if role is None or (role.tenant_id is not None and role.tenant_id != tenant_id):
        raise NotFoundError("Role not found for this tenant.")

    raw_token = generate_opaque_token()
    invitation = InvitationRepository(db).create(
        tenant_id=tenant_id, email=email.lower(), role_id=role_id, token_hash=hash_token(raw_token),
        invited_by=invited_by, expires_at=_utcnow() + INVITATION_TTL,
    )
    log_event(
        db, tenant_id=tenant_id, actor_user_id=invited_by, action="invitation.created",
        entity_type="invitation", entity_id=invitation.id, after={"email": email, "role_id": str(role_id)},
    )
    invite_url = f"{settings.api_base_url}/accept-invitation?token={raw_token}"
    send_invitation_email(to=email, tenant_name=tenant_name, invite_url=invite_url)
    return invitation


def accept_invitation(
    db: Session, *, token: str, password: str, first_name: str, last_name: str
) -> tuple[User, Invitation]:
    invitation_repo = InvitationRepository(db)
    invitation = invitation_repo.get_by_token_hash(hash_token(token))
    if invitation is None:
        raise NotFoundError("Invitation not found or already used.")
    if invitation.accepted_at is not None or invitation.revoked_at is not None:
        raise ConflictError("This invitation has already been used or revoked.", code="invitation_invalid")
    if invitation.expires_at < _utcnow():
        raise ConflictError("This invitation has expired.", code="invitation_expired")

    # The invitation's token is the authorization proof for this specific
    # tenant — now that it has been validated, the rest of this operation
    # (checking for an existing membership, creating one) proceeds under
    # that tenant's RLS context. There is no session yet (the user isn't
    # authenticated until this call succeeds), so nothing else could have
    # set this.
    set_rls_context(db, tenant_id=invitation.tenant_id, is_platform_admin=False)

    user_repo = UserRepository(db)
    user = user_repo.get_by_email(invitation.email)
    if user is None:
        user = user_repo.create(
            email=invitation.email, password_hash=hash_password(password),
            first_name=first_name, last_name=last_name,
        )
        user.email_verified = True  # accepting a targeted email invitation proves control of the inbox
    else:
        # Existing platform user accepting an invite to a new tenant — do
        # not overwrite their existing password.
        pass

    membership_repo = MembershipRepository(db)
    if membership_repo.get(invitation.tenant_id, user.id) is not None:
        raise ConflictError("You are already a member of this tenant.", code="already_member")

    membership_repo.create(
        tenant_id=invitation.tenant_id, user_id=user.id, role_id=invitation.role_id, status=MembershipStatus.ACTIVE
    )
    invitation.accepted_at = _utcnow()

    log_event(
        db, tenant_id=invitation.tenant_id, actor_user_id=user.id, action="invitation.accepted",
        entity_type="invitation", entity_id=invitation.id,
    )
    return user, invitation


# ---------------------------------------------------------------------------
# Login / logout / sessions
# ---------------------------------------------------------------------------

def authenticate(db: Session, *, email: str, password: str, ip_address: str) -> User:
    """Verifies credentials. Always raises the same generic error on any
    failure (unknown email, wrong password, inactive user) so responses
    do not leak which case occurred."""
    user_repo = UserRepository(db)
    attempt_repo = LoginAttemptRepository(db)
    user = user_repo.get_by_email(email.lower())

    generic_error = UnauthorizedError("Invalid email or password.", code="invalid_credentials")

    if user is None or not user.is_active:
        attempt_repo.record(email=email.lower(), ip_address=ip_address, success=False)
        raise generic_error

    if not verify_password(password, user.password_hash):
        attempt_repo.record(email=email.lower(), ip_address=ip_address, success=False)
        raise generic_error

    attempt_repo.record(email=email.lower(), ip_address=ip_address, success=True)
    return user


def create_session(
    db: Session, *, user: User, active_tenant_id: uuid.UUID | None, ip_address: str | None, user_agent: str | None
) -> tuple[SessionModel, str]:
    raw_token = generate_opaque_token()
    session = SessionRepository(db).create(
        user_id=user.id, session_token_hash=hash_token(raw_token), active_tenant_id=active_tenant_id,
        ip_address=ip_address, user_agent=user_agent,
        expires_at=_utcnow() + timedelta(hours=settings.session_absolute_ttl_hours),
    )
    log_event(db, tenant_id=active_tenant_id, actor_user_id=user.id, action="session.created", entity_type="session", entity_id=session.id)
    return session, raw_token


def get_session_by_raw_token(db: Session, raw_token: str) -> SessionModel | None:
    session = SessionRepository(db).get_by_token_hash(hash_token(raw_token))
    if session is None:
        return None
    if session.revoked_at is not None:
        return None
    if session.expires_at < _utcnow():
        return None
    idle_deadline = session.last_seen_at + timedelta(minutes=settings.session_idle_ttl_minutes)
    if idle_deadline < _utcnow():
        return None
    return session


def touch_session(db: Session, session: SessionModel) -> None:
    session.last_seen_at = _utcnow()


def revoke_session(db: Session, session: SessionModel) -> None:
    SessionRepository(db).revoke(session, revoked_at=_utcnow())
    log_event(
        db, tenant_id=session.active_tenant_id, actor_user_id=session.user_id,
        action="session.revoked", entity_type="session", entity_id=session.id,
    )


def revoke_all_sessions_for_user(db: Session, user_id: uuid.UUID, *, except_session_id: uuid.UUID | None = None) -> None:
    SessionRepository(db).revoke_all_for_user(user_id, revoked_at=_utcnow(), except_session_id=except_session_id)
    log_event(db, tenant_id=None, actor_user_id=user_id, action="session.revoked_all", entity_type="user", entity_id=user_id)


def switch_active_tenant(db: Session, *, session: SessionModel, user_id: uuid.UUID, tenant_id: uuid.UUID) -> SessionModel:
    membership = MembershipRepository(db).get(tenant_id, user_id)
    if membership is None or membership.status != MembershipStatus.ACTIVE:
        raise ForbiddenError("You are not an active member of this tenant.", code="not_a_member")
    tenant = tenancy_service.get_tenant_or_404(db, tenant_id)
    if tenant.status == TenantStatus.ARCHIVED:
        raise ForbiddenError("This tenant has been archived.", code="tenant_archived")
    session.active_tenant_id = tenant_id
    return session


def list_user_memberships_with_tenant(db: Session, user_id: uuid.UUID) -> list[dict]:
    memberships = MembershipRepository(db).list_for_user(user_id)
    results = []
    for membership in memberships:
        tenant = tenancy_service.get_tenant(db, membership.tenant_id)
        role = permissions_service.get_role(db, membership.role_id)
        if tenant is None or role is None:
            continue
        results.append(
            {
                "tenant_id": tenant.id,
                "tenant_name": tenant.name,
                "tenant_slug": tenant.slug,
                "role_name": role.name,
            }
        )
    return results


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------

def request_email_verification(db: Session, *, user: User) -> None:
    if user.email_verified:
        return
    raw_token = generate_opaque_token()
    TokenRepository(db).create_email_verification_token(
        user_id=user.id, token_hash=hash_token(raw_token), expires_at=_utcnow() + EMAIL_VERIFICATION_TTL
    )
    verify_url = f"{settings.api_base_url}/verify-email?token={raw_token}"
    send_verification_email(to=user.email, verify_url=verify_url)


def verify_email(db: Session, *, token: str) -> User:
    token_repo = TokenRepository(db)
    record = token_repo.get_email_verification_token(hash_token(token))
    if record is None or record.used_at is not None or record.expires_at < _utcnow():
        raise ConflictError("This verification link is invalid or has expired.", code="verification_invalid")
    user = UserRepository(db).get_by_id(record.user_id)
    if user is None:
        raise NotFoundError("User not found.")
    user.email_verified = True
    record.used_at = _utcnow()
    log_event(db, tenant_id=None, actor_user_id=user.id, action="user.email_verified", entity_type="user", entity_id=user.id)
    return user


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------

def request_password_reset(db: Session, *, email: str) -> None:
    """Always returns silently regardless of whether the email exists, to
    avoid account enumeration. Only sends an email when a matching, active
    user is found."""
    user = UserRepository(db).get_by_email(email.lower())
    if user is None or not user.is_active:
        return
    raw_token = generate_opaque_token()
    TokenRepository(db).create_password_reset_token(
        user_id=user.id, token_hash=hash_token(raw_token), expires_at=_utcnow() + PASSWORD_RESET_TTL
    )
    reset_url = f"{settings.api_base_url}/reset-password?token={raw_token}"
    send_password_reset_email(to=user.email, reset_url=reset_url)


def reset_password(db: Session, *, token: str, new_password: str) -> User:
    token_repo = TokenRepository(db)
    record = token_repo.get_password_reset_token(hash_token(token))
    if record is None or record.used_at is not None or record.expires_at < _utcnow():
        raise ConflictError("This password reset link is invalid or has expired.", code="reset_invalid")
    user = UserRepository(db).get_by_id(record.user_id)
    if user is None:
        raise NotFoundError("User not found.")

    user.password_hash = hash_password(new_password)
    record.used_at = _utcnow()
    # A successful reset revokes every existing session — the whole point
    # of a reset is that prior credentials/sessions should no longer work.
    revoke_all_sessions_for_user(db, user.id)
    log_event(db, tenant_id=None, actor_user_id=user.id, action="user.password_reset", entity_type="user", entity_id=user.id)
    return user
