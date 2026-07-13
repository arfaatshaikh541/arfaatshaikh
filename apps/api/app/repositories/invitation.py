import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.invitation import Invitation


class InvitationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        tenant_id: uuid.UUID,
        email: str,
        role_id: uuid.UUID,
        invited_by_user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> Invitation:
        invitation = Invitation(
            tenant_id=tenant_id,
            email=email.lower(),
            role_id=role_id,
            invited_by_user_id=invited_by_user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.db.add(invitation)
        self.db.flush()
        return invitation

    def get_by_token_hash(self, token_hash: str) -> Invitation | None:
        stmt = select(Invitation).where(Invitation.token_hash == token_hash)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_id_for_tenant(
        self, tenant_id: uuid.UUID, invitation_id: uuid.UUID
    ) -> Invitation | None:
        stmt = select(Invitation).where(
            Invitation.tenant_id == tenant_id, Invitation.id == invitation_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[Invitation]:
        stmt = (
            select(Invitation)
            .where(Invitation.tenant_id == tenant_id)
            .order_by(Invitation.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def mark_status(self, invitation: Invitation, status: str) -> Invitation:
        invitation.status = status
        self.db.flush()
        return invitation
