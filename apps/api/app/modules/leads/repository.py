import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.leads.models import (
    Lead,
    LeadSource,
    QualificationAnswer,
    QualificationForm,
    QualificationOption,
    QualificationQuestion,
    Service,
    ServiceCategory,
)


class ServiceCategoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[ServiceCategory]:
        return list(
            self.db.execute(
                select(ServiceCategory).where(ServiceCategory.tenant_id == tenant_id).order_by(ServiceCategory.sort_order)
            )
            .scalars()
            .all()
        )

    def create(self, *, tenant_id: uuid.UUID, name: str, sort_order: int = 0) -> ServiceCategory:
        category = ServiceCategory(tenant_id=tenant_id, name=name, sort_order=sort_order)
        self.db.add(category)
        self.db.flush()
        return category


class ServiceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, service_id: uuid.UUID) -> Service | None:
        return self.db.execute(
            select(Service).where(Service.tenant_id == tenant_id, Service.id == service_id)
        ).scalar_one_or_none()

    def list_for_tenant(self, tenant_id: uuid.UUID, *, active_only: bool = False) -> list[Service]:
        stmt = select(Service).where(Service.tenant_id == tenant_id)
        if active_only:
            stmt = stmt.where(Service.is_active.is_(True))
        return list(self.db.execute(stmt.order_by(Service.sort_order)).scalars().all())

    def create(
        self, *, tenant_id: uuid.UUID, name: str, description: str = "", category_id: uuid.UUID | None = None, sort_order: int = 0
    ) -> Service:
        service = Service(tenant_id=tenant_id, name=name, description=description, category_id=category_id, sort_order=sort_order)
        self.db.add(service)
        self.db.flush()
        return service


class QualificationFormRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, form_id: uuid.UUID) -> QualificationForm | None:
        return self.db.execute(
            select(QualificationForm).where(QualificationForm.tenant_id == tenant_id, QualificationForm.id == form_id)
        ).scalar_one_or_none()

    def get_for_service(self, tenant_id: uuid.UUID, service_id: uuid.UUID | None) -> QualificationForm | None:
        """The service's own form if one exists and is active, else the
        tenant's default (service_id IS NULL) active form."""
        if service_id is not None:
            specific = self.db.execute(
                select(QualificationForm).where(
                    QualificationForm.tenant_id == tenant_id,
                    QualificationForm.service_id == service_id,
                    QualificationForm.is_active.is_(True),
                )
            ).scalar_one_or_none()
            if specific is not None:
                return specific
        return self.db.execute(
            select(QualificationForm).where(
                QualificationForm.tenant_id == tenant_id,
                QualificationForm.service_id.is_(None),
                QualificationForm.is_active.is_(True),
            )
        ).scalar_one_or_none()

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[QualificationForm]:
        return list(
            self.db.execute(select(QualificationForm).where(QualificationForm.tenant_id == tenant_id)).scalars().all()
        )

    def create(self, *, tenant_id: uuid.UUID, name: str, service_id: uuid.UUID | None = None) -> QualificationForm:
        form = QualificationForm(tenant_id=tenant_id, name=name, service_id=service_id)
        self.db.add(form)
        self.db.flush()
        return form


class QualificationQuestionRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_form(self, tenant_id: uuid.UUID, form_id: uuid.UUID) -> list[QualificationQuestion]:
        return list(
            self.db.execute(
                select(QualificationQuestion)
                .where(QualificationQuestion.tenant_id == tenant_id, QualificationQuestion.form_id == form_id)
                .order_by(QualificationQuestion.sort_order)
            )
            .scalars()
            .all()
        )

    def get(self, tenant_id: uuid.UUID, question_id: uuid.UUID) -> QualificationQuestion | None:
        return self.db.execute(
            select(QualificationQuestion).where(
                QualificationQuestion.tenant_id == tenant_id, QualificationQuestion.id == question_id
            )
        ).scalar_one_or_none()

    def create(
        self, *, tenant_id: uuid.UUID, form_id: uuid.UUID, label: str, question_type, is_required: bool,
        sort_order: int, maps_to_field: str | None = None,
    ) -> QualificationQuestion:
        question = QualificationQuestion(
            tenant_id=tenant_id, form_id=form_id, label=label, question_type=question_type,
            is_required=is_required, sort_order=sort_order, maps_to_field=maps_to_field,
        )
        self.db.add(question)
        self.db.flush()
        return question

    def reorder(self, questions_in_order: list[QualificationQuestion]) -> None:
        for index, question in enumerate(questions_in_order):
            question.sort_order = index
        self.db.flush()


class QualificationOptionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, tenant_id: uuid.UUID, question_id: uuid.UUID, label: str, value: str, sort_order: int = 0) -> QualificationOption:
        option = QualificationOption(tenant_id=tenant_id, question_id=question_id, label=label, value=value, sort_order=sort_order)
        self.db.add(option)
        self.db.flush()
        return option

    def list_for_question(self, question_id: uuid.UUID) -> list[QualificationOption]:
        return list(
            self.db.execute(
                select(QualificationOption).where(QualificationOption.question_id == question_id).order_by(QualificationOption.sort_order)
            )
            .scalars()
            .all()
        )


class QualificationAnswerRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, question_id: uuid.UUID, question_label: str,
        answer_value, created_at: datetime,
    ) -> QualificationAnswer:
        answer = QualificationAnswer(
            tenant_id=tenant_id, lead_id=lead_id, question_id=question_id, question_label=question_label,
            answer_value=answer_value, created_at=created_at,
        )
        self.db.add(answer)
        self.db.flush()
        return answer

    def list_for_lead(self, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> list[QualificationAnswer]:
        return list(
            self.db.execute(
                select(QualificationAnswer)
                .where(QualificationAnswer.tenant_id == tenant_id, QualificationAnswer.lead_id == lead_id)
                .order_by(QualificationAnswer.created_at)
            )
            .scalars()
            .all()
        )


class LeadSourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_code(self, tenant_id: uuid.UUID, code: str) -> LeadSource | None:
        return self.db.execute(
            select(LeadSource).where(LeadSource.tenant_id == tenant_id, LeadSource.code == code)
        ).scalar_one_or_none()

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[LeadSource]:
        return list(self.db.execute(select(LeadSource).where(LeadSource.tenant_id == tenant_id)).scalars().all())

    def create(self, *, tenant_id: uuid.UUID, code: str, name: str) -> LeadSource:
        source = LeadSource(tenant_id=tenant_id, code=code, name=name)
        self.db.add(source)
        self.db.flush()
        return source


class LeadRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> Lead | None:
        return self.db.execute(select(Lead).where(Lead.tenant_id == tenant_id, Lead.id == lead_id)).scalar_one_or_none()

    def create(self, **fields) -> Lead:
        lead = Lead(**fields)
        self.db.add(lead)
        self.db.flush()
        return lead

    def find_possible_duplicate(self, tenant_id: uuid.UUID, *, email: str | None, phone: str | None, within: timedelta) -> Lead | None:
        if not email and not phone:
            return None
        cutoff = datetime.now(UTC) - within
        stmt = select(Lead).where(Lead.tenant_id == tenant_id, Lead.created_at >= cutoff)
        if email and phone:
            stmt = stmt.where((Lead.email == email) | (Lead.phone == phone))
        elif email:
            stmt = stmt.where(Lead.email == email)
        else:
            stmt = stmt.where(Lead.phone == phone)
        return self.db.execute(stmt.order_by(Lead.created_at.desc())).scalars().first()

    def get_by_idempotency_key(self, tenant_id: uuid.UUID, key: str) -> Lead | None:
        return self.db.execute(
            select(Lead).where(Lead.tenant_id == tenant_id, Lead.idempotency_key == key)
        ).scalar_one_or_none()

    def search(
        self, tenant_id: uuid.UUID, *, stage_id: uuid.UUID | None = None, assigned_user_id: uuid.UUID | None = None,
        service_id: uuid.UUID | None = None, query: str | None = None, include_archived: bool = False,
    ):
        stmt = select(Lead).where(Lead.tenant_id == tenant_id)
        if not include_archived:
            stmt = stmt.where(Lead.is_archived.is_(False))
        if stage_id:
            stmt = stmt.where(Lead.stage_id == stage_id)
        if assigned_user_id:
            stmt = stmt.where(Lead.assigned_user_id == assigned_user_id)
        if service_id:
            stmt = stmt.where(Lead.service_id == service_id)
        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                (Lead.first_name.ilike(like))
                | (Lead.last_name.ilike(like))
                | (Lead.email.ilike(like))
                | (Lead.phone.ilike(like))
                | (Lead.company.ilike(like))
                | (Lead.reference_number.ilike(like))
            )
        return stmt.order_by(Lead.created_at.desc())

    def count_for_tenant(self, tenant_id: uuid.UUID, *, include_archived: bool = False) -> int:
        stmt = select(Lead).where(Lead.tenant_id == tenant_id)
        if not include_archived:
            stmt = stmt.where(Lead.is_archived.is_(False))
        return len(self.db.execute(stmt).scalars().all())
