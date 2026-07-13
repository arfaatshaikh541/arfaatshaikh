import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.lead import Lead, LeadAnswer, LeadNote, LeadStageHistory, LeadTagLink


@dataclass
class LeadFilters:
    stage_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    source: str | None = None
    priority: str | None = None
    assigned_membership_id: uuid.UUID | None = None
    tag_id: uuid.UUID | None = None
    search: str | None = None


@dataclass
class LeadPage:
    items: list[Lead] = field(default_factory=list)
    total: int = 0


class LeadRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id_for_tenant(self, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> Lead | None:
        stmt = select(Lead).where(Lead.tenant_id == tenant_id, Lead.id == lead_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_tenant(
        self, tenant_id: uuid.UUID, *, filters: LeadFilters, page: int, page_size: int
    ) -> LeadPage:
        stmt = select(Lead).where(Lead.tenant_id == tenant_id)
        stmt = self._apply_filters(stmt, filters)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self.db.execute(count_stmt).scalar_one())

        stmt = stmt.order_by(Lead.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())
        return LeadPage(items=items, total=total)

    def _apply_filters(self, stmt, filters: LeadFilters):  # type: ignore[no-untyped-def]
        if filters.stage_id:
            stmt = stmt.where(Lead.stage_id == filters.stage_id)
        if filters.service_id:
            stmt = stmt.where(Lead.service_id == filters.service_id)
        if filters.branch_id:
            stmt = stmt.where(Lead.branch_id == filters.branch_id)
        if filters.source:
            stmt = stmt.where(Lead.source == filters.source)
        if filters.priority:
            stmt = stmt.where(Lead.priority == filters.priority)
        if filters.assigned_membership_id:
            stmt = stmt.where(Lead.assigned_membership_id == filters.assigned_membership_id)
        if filters.tag_id:
            stmt = stmt.join(LeadTagLink, LeadTagLink.lead_id == Lead.id).where(
                LeadTagLink.tag_id == filters.tag_id
            )
        if filters.search:
            pattern = f"%{filters.search.strip()}%"
            stmt = stmt.where(
                or_(
                    Lead.first_name.ilike(pattern),
                    Lead.last_name.ilike(pattern),
                    Lead.email.ilike(pattern),
                    Lead.phone.ilike(pattern),
                    Lead.company.ilike(pattern),
                    Lead.reference_number.ilike(pattern),
                )
            )
        return stmt

    def find_possible_duplicate(
        self, tenant_id: uuid.UUID, *, email: str | None, phone: str | None, window_days: int = 30
    ) -> Lead | None:
        if not email and not phone:
            return None
        from datetime import timedelta

        since = utcnow() - timedelta(days=window_days)
        conditions = []
        if email:
            conditions.append(Lead.email == email)
        if phone:
            conditions.append(Lead.phone == phone)
        stmt = (
            select(Lead)
            .where(Lead.tenant_id == tenant_id, Lead.created_at >= since, or_(*conditions))
            .order_by(Lead.created_at.desc())
        )
        return self.db.execute(stmt).scalars().first()

    def get_by_reference_for_tenant(
        self, tenant_id: uuid.UUID, reference_number: str
    ) -> Lead | None:
        stmt = select(Lead).where(
            Lead.tenant_id == tenant_id, Lead.reference_number == reference_number
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, lead: Lead) -> Lead:
        self.db.add(lead)
        self.db.flush()
        return lead


class LeadAnswerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        lead_id: uuid.UUID,
        question_id: uuid.UUID | None,
        question_label_snapshot: str,
        field_type_snapshot: str,
        value: object,
    ) -> LeadAnswer:
        answer = LeadAnswer(
            lead_id=lead_id,
            question_id=question_id,
            question_label_snapshot=question_label_snapshot,
            field_type_snapshot=field_type_snapshot,
            value=value,
            created_at=utcnow(),
        )
        self.db.add(answer)
        self.db.flush()
        return answer

    def list_for_lead(self, lead_id: uuid.UUID) -> list[LeadAnswer]:
        stmt = select(LeadAnswer).where(LeadAnswer.lead_id == lead_id)
        return list(self.db.execute(stmt).scalars().all())


class LeadNoteRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, lead_id: uuid.UUID, author_user_id: uuid.UUID, body: str) -> LeadNote:
        note = LeadNote(
            lead_id=lead_id, author_user_id=author_user_id, body=body, created_at=utcnow()
        )
        self.db.add(note)
        self.db.flush()
        return note

    def list_for_lead(self, lead_id: uuid.UUID) -> list[LeadNote]:
        stmt = (
            select(LeadNote).where(LeadNote.lead_id == lead_id).order_by(LeadNote.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())


class LeadStageHistoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        lead_id: uuid.UUID,
        from_stage_id: uuid.UUID | None,
        to_stage_id: uuid.UUID,
        changed_by_user_id: uuid.UUID | None,
        reason: str | None = None,
    ) -> LeadStageHistory:
        entry = LeadStageHistory(
            lead_id=lead_id,
            from_stage_id=from_stage_id,
            to_stage_id=to_stage_id,
            changed_by_user_id=changed_by_user_id,
            reason=reason,
            created_at=utcnow(),
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_for_lead(self, lead_id: uuid.UUID) -> list[LeadStageHistory]:
        stmt = (
            select(LeadStageHistory)
            .where(LeadStageHistory.lead_id == lead_id)
            .order_by(LeadStageHistory.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())


class LeadTagRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, *, lead_id: uuid.UUID, tag_id: uuid.UUID) -> LeadTagLink | None:
        existing = self.db.get(LeadTagLink, (lead_id, tag_id))
        if existing:
            return None
        link = LeadTagLink(lead_id=lead_id, tag_id=tag_id)
        self.db.add(link)
        self.db.flush()
        return link

    def remove(self, *, lead_id: uuid.UUID, tag_id: uuid.UUID) -> bool:
        existing = self.db.get(LeadTagLink, (lead_id, tag_id))
        if existing is None:
            return False
        self.db.delete(existing)
        self.db.flush()
        return True
