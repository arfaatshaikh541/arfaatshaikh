import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.onboarding.models import (
    OnboardingCase,
    OnboardingCaseStep,
    OnboardingTemplate,
    OnboardingTemplateStep,
)


class OnboardingTemplateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, template_id: uuid.UUID) -> OnboardingTemplate | None:
        return self.db.execute(
            select(OnboardingTemplate).where(OnboardingTemplate.tenant_id == tenant_id, OnboardingTemplate.id == template_id)
        ).scalar_one_or_none()

    def list_for_tenant(self, tenant_id: uuid.UUID, *, active_only: bool = False) -> list[OnboardingTemplate]:
        stmt = select(OnboardingTemplate).where(OnboardingTemplate.tenant_id == tenant_id)
        if active_only:
            stmt = stmt.where(OnboardingTemplate.is_active.is_(True))
        return list(self.db.execute(stmt.order_by(OnboardingTemplate.sort_order)).scalars().all())

    def create(self, *, tenant_id: uuid.UUID, name: str, description: str = "", sort_order: int = 0) -> OnboardingTemplate:
        template = OnboardingTemplate(tenant_id=tenant_id, name=name, description=description, sort_order=sort_order)
        self.db.add(template)
        self.db.flush()
        return template


class OnboardingTemplateStepRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_template(self, tenant_id: uuid.UUID, template_id: uuid.UUID) -> list[OnboardingTemplateStep]:
        return list(
            self.db.execute(
                select(OnboardingTemplateStep)
                .where(OnboardingTemplateStep.tenant_id == tenant_id, OnboardingTemplateStep.template_id == template_id)
                .order_by(OnboardingTemplateStep.sort_order)
            )
            .scalars()
            .all()
        )

    def create(
        self, *, tenant_id: uuid.UUID, template_id: uuid.UUID, sort_order: int, step_type, title: str,
        description: str = "", due_in_days: int | None = None,
    ) -> OnboardingTemplateStep:
        step = OnboardingTemplateStep(
            tenant_id=tenant_id, template_id=template_id, sort_order=sort_order, step_type=step_type,
            title=title, description=description, due_in_days=due_in_days,
        )
        self.db.add(step)
        self.db.flush()
        return step


class OnboardingCaseRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, case_id: uuid.UUID) -> OnboardingCase | None:
        return self.db.execute(
            select(OnboardingCase).where(OnboardingCase.tenant_id == tenant_id, OnboardingCase.id == case_id)
        ).scalar_one_or_none()

    def list_for_lead(self, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> list[OnboardingCase]:
        return list(
            self.db.execute(
                select(OnboardingCase)
                .where(OnboardingCase.tenant_id == tenant_id, OnboardingCase.lead_id == lead_id)
                .order_by(OnboardingCase.created_at.desc())
            )
            .scalars()
            .all()
        )

    def list_for_tenant(self, tenant_id: uuid.UUID, *, status=None) -> list[OnboardingCase]:
        stmt = select(OnboardingCase).where(OnboardingCase.tenant_id == tenant_id)
        if status is not None:
            stmt = stmt.where(OnboardingCase.status == status)
        return list(self.db.execute(stmt.order_by(OnboardingCase.created_at.desc())).scalars().all())

    def create(self, **fields) -> OnboardingCase:
        case = OnboardingCase(**fields)
        self.db.add(case)
        self.db.flush()
        return case


class OnboardingCaseStepRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_case(self, tenant_id: uuid.UUID, case_id: uuid.UUID) -> list[OnboardingCaseStep]:
        return list(
            self.db.execute(
                select(OnboardingCaseStep)
                .where(OnboardingCaseStep.tenant_id == tenant_id, OnboardingCaseStep.case_id == case_id)
                .order_by(OnboardingCaseStep.sort_order)
            )
            .scalars()
            .all()
        )

    def get_by_task_id(self, tenant_id: uuid.UUID, task_id: uuid.UUID) -> OnboardingCaseStep | None:
        return self.db.execute(
            select(OnboardingCaseStep).where(OnboardingCaseStep.tenant_id == tenant_id, OnboardingCaseStep.task_id == task_id)
        ).scalar_one_or_none()

    def get_by_document_request_id(self, tenant_id: uuid.UUID, document_request_id: uuid.UUID) -> OnboardingCaseStep | None:
        return self.db.execute(
            select(OnboardingCaseStep).where(
                OnboardingCaseStep.tenant_id == tenant_id, OnboardingCaseStep.document_request_id == document_request_id
            )
        ).scalar_one_or_none()

    def create(self, **fields) -> OnboardingCaseStep:
        step = OnboardingCaseStep(**fields)
        self.db.add(step)
        self.db.flush()
        return step
