import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.branch import Branch


class BranchRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_tenant(self, tenant_id: uuid.UUID, *, active_only: bool = False) -> list[Branch]:
        stmt = select(Branch).where(Branch.tenant_id == tenant_id)
        if active_only:
            stmt = stmt.where(Branch.is_active.is_(True))
        stmt = stmt.order_by(Branch.name)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id_for_tenant(self, tenant_id: uuid.UUID, branch_id: uuid.UUID) -> Branch | None:
        stmt = select(Branch).where(Branch.tenant_id == tenant_id, Branch.id == branch_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, *, tenant_id: uuid.UUID, name: str) -> Branch:
        branch = Branch(tenant_id=tenant_id, name=name)
        self.db.add(branch)
        self.db.flush()
        return branch
