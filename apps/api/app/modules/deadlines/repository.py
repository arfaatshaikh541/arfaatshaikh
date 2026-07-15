import uuid
from datetime import date as date_

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.deadlines.models import Deadline, DeadlineStatus


class DeadlineRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, deadline_id: uuid.UUID) -> Deadline | None:
        return self.db.execute(
            select(Deadline).where(Deadline.tenant_id == tenant_id, Deadline.id == deadline_id)
        ).scalar_one_or_none()

    def list_for_lead(self, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> list[Deadline]:
        return list(
            self.db.execute(
                select(Deadline).where(Deadline.tenant_id == tenant_id, Deadline.lead_id == lead_id).order_by(Deadline.due_date)
            )
            .scalars()
            .all()
        )

    def list_for_tenant(self, tenant_id: uuid.UUID, *, status: DeadlineStatus | None = None) -> list[Deadline]:
        stmt = select(Deadline).where(Deadline.tenant_id == tenant_id)
        if status is not None:
            stmt = stmt.where(Deadline.status == status)
        return list(self.db.execute(stmt.order_by(Deadline.due_date)).scalars().all())

    def list_due_for_reminder(self, *, tenant_id: uuid.UUID, on_or_before: date_) -> list[Deadline]:
        return list(
            self.db.execute(
                select(Deadline).where(
                    Deadline.tenant_id == tenant_id,
                    Deadline.status == DeadlineStatus.OPEN,
                    Deadline.due_date <= on_or_before,
                    Deadline.reminder_sent_at.is_(None),
                )
            )
            .scalars()
            .all()
        )

    def create(self, **fields) -> Deadline:
        deadline = Deadline(**fields)
        self.db.add(deadline)
        self.db.flush()
        return deadline
