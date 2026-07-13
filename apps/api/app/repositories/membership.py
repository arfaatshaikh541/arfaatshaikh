import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.membership import Membership


class MembershipRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_user_and_tenant(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Membership | None:
        stmt = select(Membership).where(
            Membership.user_id == user_id, Membership.tenant_id == tenant_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_user(self, user_id: uuid.UUID) -> list[Membership]:
        stmt = select(Membership).where(Membership.user_id == user_id)
        return list(self.db.execute(stmt).scalars().all())

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[Membership]:
        stmt = select(Membership).where(Membership.tenant_id == tenant_id)
        return list(self.db.execute(stmt).scalars().all())

    def create(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        role_id: uuid.UUID,
        status: str = "active",
    ) -> Membership:
        membership = Membership(
            tenant_id=tenant_id, user_id=user_id, role_id=role_id, status=status
        )
        self.db.add(membership)
        self.db.flush()
        return membership

    def get_by_id_for_tenant(
        self, tenant_id: uuid.UUID, membership_id: uuid.UUID
    ) -> Membership | None:
        stmt = select(Membership).where(
            Membership.tenant_id == tenant_id, Membership.id == membership_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def update_role(self, membership: Membership, role_id: uuid.UUID) -> Membership:
        membership.role_id = role_id
        self.db.flush()
        return membership

    def update_status(self, membership: Membership, status: str) -> Membership:
        membership.status = status
        self.db.flush()
        return membership
