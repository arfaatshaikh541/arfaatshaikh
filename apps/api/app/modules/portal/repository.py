import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.portal.models import (
    PortalAccount,
    PortalInvitation,
    PortalPasswordResetToken,
    PortalSession,
)


class PortalAccountRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, account_id: uuid.UUID) -> PortalAccount | None:
        return self.db.execute(
            select(PortalAccount).where(PortalAccount.tenant_id == tenant_id, PortalAccount.id == account_id)
        ).scalar_one_or_none()

    def get_by_email(self, tenant_id: uuid.UUID, email: str) -> PortalAccount | None:
        return self.db.execute(
            select(PortalAccount).where(PortalAccount.tenant_id == tenant_id, PortalAccount.email == email)
        ).scalar_one_or_none()

    def get_by_lead(self, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> PortalAccount | None:
        return self.db.execute(
            select(PortalAccount).where(PortalAccount.tenant_id == tenant_id, PortalAccount.lead_id == lead_id)
        ).scalar_one_or_none()

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[PortalAccount]:
        return list(self.db.execute(select(PortalAccount).where(PortalAccount.tenant_id == tenant_id)).scalars().all())

    def create(self, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, email: str, password_hash: str) -> PortalAccount:
        account = PortalAccount(tenant_id=tenant_id, lead_id=lead_id, email=email, password_hash=password_hash)
        self.db.add(account)
        self.db.flush()
        return account


class PortalInvitationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, email: str, token_hash: str,
        invited_by: uuid.UUID | None, expires_at: datetime,
    ) -> PortalInvitation:
        invitation = PortalInvitation(
            tenant_id=tenant_id, lead_id=lead_id, email=email, token_hash=token_hash,
            invited_by=invited_by, expires_at=expires_at,
        )
        self.db.add(invitation)
        self.db.flush()
        return invitation

    def get_by_token_hash(self, token_hash: str) -> PortalInvitation | None:
        return self.db.execute(select(PortalInvitation).where(PortalInvitation.token_hash == token_hash)).scalar_one_or_none()

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[PortalInvitation]:
        return list(self.db.execute(select(PortalInvitation).where(PortalInvitation.tenant_id == tenant_id)).scalars().all())

    def list_expired_unaccepted(self, before: datetime) -> list[PortalInvitation]:
        return list(
            self.db.execute(
                select(PortalInvitation).where(
                    PortalInvitation.accepted_at.is_(None),
                    PortalInvitation.revoked_at.is_(None),
                    PortalInvitation.expires_at < before,
                )
            )
            .scalars()
            .all()
        )


class PortalSessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, *, tenant_id: uuid.UUID, portal_account_id: uuid.UUID, session_token_hash: str,
        ip_address: str | None, user_agent: str | None, expires_at: datetime,
    ) -> PortalSession:
        session = PortalSession(
            tenant_id=tenant_id, portal_account_id=portal_account_id, session_token_hash=session_token_hash,
            ip_address=ip_address, user_agent=user_agent, expires_at=expires_at,
        )
        self.db.add(session)
        self.db.flush()
        return session

    def get_by_token_hash(self, token_hash: str) -> PortalSession | None:
        return self.db.execute(select(PortalSession).where(PortalSession.session_token_hash == token_hash)).scalar_one_or_none()

    def revoke(self, session: PortalSession, *, revoked_at: datetime) -> None:
        session.revoked_at = revoked_at

    def revoke_all_for_account(self, portal_account_id: uuid.UUID, *, revoked_at: datetime) -> None:
        sessions = self.db.execute(
            select(PortalSession).where(PortalSession.portal_account_id == portal_account_id, PortalSession.revoked_at.is_(None))
        ).scalars().all()
        for session in sessions:
            session.revoked_at = revoked_at

    def list_expired(self, before: datetime) -> list[PortalSession]:
        return list(self.db.execute(select(PortalSession).where(PortalSession.expires_at < before)).scalars().all())

    def delete(self, session: PortalSession) -> None:
        self.db.delete(session)


class PortalPasswordResetTokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, tenant_id: uuid.UUID, portal_account_id: uuid.UUID, token_hash: str, expires_at: datetime) -> PortalPasswordResetToken:
        token = PortalPasswordResetToken(tenant_id=tenant_id, portal_account_id=portal_account_id, token_hash=token_hash, expires_at=expires_at)
        self.db.add(token)
        self.db.flush()
        return token

    def get_by_token_hash(self, token_hash: str) -> PortalPasswordResetToken | None:
        return self.db.execute(
            select(PortalPasswordResetToken).where(PortalPasswordResetToken.token_hash == token_hash)
        ).scalar_one_or_none()
