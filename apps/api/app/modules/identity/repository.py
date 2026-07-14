import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.models import (
    EmailVerificationToken,
    Invitation,
    LoginAttempt,
    Membership,
    MembershipStatus,
    PasswordResetToken,
    User,
)
from app.modules.identity.models import (
    Session as SessionModel,
)


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.db.execute(select(User).where(User.email == email)).scalar_one_or_none()

    def create(self, *, email: str, password_hash: str, first_name: str, last_name: str) -> User:
        user = User(email=email, password_hash=password_hash, first_name=first_name, last_name=last_name)
        self.db.add(user)
        self.db.flush()
        return user


class MembershipRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> Membership | None:
        return self.db.execute(
            select(Membership).where(Membership.tenant_id == tenant_id, Membership.user_id == user_id)
        ).scalar_one_or_none()

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[Membership]:
        return list(self.db.execute(select(Membership).where(Membership.tenant_id == tenant_id)).scalars().all())

    def list_for_user(self, user_id: uuid.UUID) -> list[Membership]:
        return list(
            self.db.execute(
                select(Membership).where(
                    Membership.user_id == user_id, Membership.status == MembershipStatus.ACTIVE
                )
            )
            .scalars()
            .all()
        )

    def count_active_for_tenant(self, tenant_id: uuid.UUID) -> int:
        return len(
            self.db.execute(
                select(Membership).where(
                    Membership.tenant_id == tenant_id, Membership.status == MembershipStatus.ACTIVE
                )
            )
            .scalars()
            .all()
        )

    def create(self, *, tenant_id: uuid.UUID, user_id: uuid.UUID, role_id: uuid.UUID, status: MembershipStatus) -> Membership:
        membership = Membership(tenant_id=tenant_id, user_id=user_id, role_id=role_id, status=status)
        self.db.add(membership)
        self.db.flush()
        return membership


class InvitationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, *, tenant_id: uuid.UUID, email: str, role_id: uuid.UUID, token_hash: str, invited_by: uuid.UUID, expires_at: datetime
    ) -> Invitation:
        invitation = Invitation(
            tenant_id=tenant_id, email=email, role_id=role_id, token_hash=token_hash,
            invited_by=invited_by, expires_at=expires_at,
        )
        self.db.add(invitation)
        self.db.flush()
        return invitation

    def get_by_token_hash(self, token_hash: str) -> Invitation | None:
        return self.db.execute(
            select(Invitation).where(Invitation.token_hash == token_hash)
        ).scalar_one_or_none()

    def list_expired_unaccepted(self, before: datetime) -> list[Invitation]:
        return list(
            self.db.execute(
                select(Invitation).where(
                    Invitation.accepted_at.is_(None),
                    Invitation.revoked_at.is_(None),
                    Invitation.expires_at < before,
                )
            )
            .scalars()
            .all()
        )


class SessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, *, user_id: uuid.UUID, session_token_hash: str, active_tenant_id: uuid.UUID | None,
        ip_address: str | None, user_agent: str | None, expires_at: datetime,
    ) -> SessionModel:
        session = SessionModel(
            user_id=user_id, session_token_hash=session_token_hash, active_tenant_id=active_tenant_id,
            ip_address=ip_address, user_agent=user_agent, expires_at=expires_at,
        )
        self.db.add(session)
        self.db.flush()
        return session

    def get_by_token_hash(self, token_hash: str) -> SessionModel | None:
        return self.db.execute(
            select(SessionModel).where(SessionModel.session_token_hash == token_hash)
        ).scalar_one_or_none()

    def revoke(self, session: SessionModel, *, revoked_at: datetime) -> None:
        session.revoked_at = revoked_at

    def revoke_all_for_user(self, user_id: uuid.UUID, *, revoked_at: datetime, except_session_id: uuid.UUID | None = None) -> None:
        sessions = self.db.execute(
            select(SessionModel).where(SessionModel.user_id == user_id, SessionModel.revoked_at.is_(None))
        ).scalars().all()
        for session in sessions:
            if except_session_id and session.id == except_session_id:
                continue
            session.revoked_at = revoked_at

    def list_expired(self, before: datetime) -> list[SessionModel]:
        return list(
            self.db.execute(select(SessionModel).where(SessionModel.expires_at < before)).scalars().all()
        )

    def delete(self, session: SessionModel) -> None:
        self.db.delete(session)


class TokenRepository:
    """Handles email-verification and password-reset single-use tokens."""

    def __init__(self, db: Session):
        self.db = db

    def create_email_verification_token(self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime) -> EmailVerificationToken:
        token = EmailVerificationToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.db.add(token)
        self.db.flush()
        return token

    def get_email_verification_token(self, token_hash: str) -> EmailVerificationToken | None:
        return self.db.execute(
            select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
        ).scalar_one_or_none()

    def create_password_reset_token(self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime) -> PasswordResetToken:
        token = PasswordResetToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.db.add(token)
        self.db.flush()
        return token

    def get_password_reset_token(self, token_hash: str) -> PasswordResetToken | None:
        return self.db.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        ).scalar_one_or_none()


class LoginAttemptRepository:
    def __init__(self, db: Session):
        self.db = db

    def record(self, *, email: str, ip_address: str, success: bool) -> None:
        self.db.add(LoginAttempt(email=email, ip_address=ip_address, success=success))
