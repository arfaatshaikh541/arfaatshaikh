import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.modules.onboarding.models import (
    OnboardingCase,
    OnboardingCaseStatus,
    OnboardingCaseStep,
    OnboardingCaseStepStatus,
    OnboardingStepType,
    OnboardingTemplate,
)
from app.modules.onboarding.repository import (
    OnboardingCaseRepository,
    OnboardingCaseStepRepository,
    OnboardingTemplateRepository,
    OnboardingTemplateStepRepository,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


# --- Templates -----------------------------------------------------------

def list_templates(db: Session, tenant_id: uuid.UUID, *, active_only: bool = False) -> list[OnboardingTemplate]:
    return OnboardingTemplateRepository(db).list_for_tenant(tenant_id, active_only=active_only)


def get_template_or_404(db: Session, tenant_id: uuid.UUID, template_id: uuid.UUID) -> OnboardingTemplate:
    template = OnboardingTemplateRepository(db).get(tenant_id, template_id)
    if template is None:
        raise NotFoundError("Onboarding template not found.")
    return template


def list_template_steps(db: Session, tenant_id: uuid.UUID, template_id: uuid.UUID):
    return OnboardingTemplateStepRepository(db).list_for_template(tenant_id, template_id)


def create_template(db: Session, *, tenant_id: uuid.UUID, name: str, description: str = "", steps: list[dict] | None = None) -> OnboardingTemplate:
    existing = OnboardingTemplateRepository(db).list_for_tenant(tenant_id)
    template = OnboardingTemplateRepository(db).create(tenant_id=tenant_id, name=name, description=description, sort_order=len(existing))
    step_repo = OnboardingTemplateStepRepository(db)
    for index, step in enumerate(steps or []):
        step_repo.create(
            tenant_id=tenant_id, template_id=template.id, sort_order=index, step_type=step["step_type"],
            title=step["title"], description=step.get("description", ""), due_in_days=step.get("due_in_days"),
        )
    return template


# --- Cases ---------------------------------------------------------------

def list_cases_for_lead(db: Session, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> list[OnboardingCase]:
    return OnboardingCaseRepository(db).list_for_lead(tenant_id, lead_id)


def list_cases_for_tenant(db: Session, tenant_id: uuid.UUID, *, status: OnboardingCaseStatus | None = None) -> list[OnboardingCase]:
    return OnboardingCaseRepository(db).list_for_tenant(tenant_id, status=status)


def get_case_or_404(db: Session, tenant_id: uuid.UUID, case_id: uuid.UUID) -> OnboardingCase:
    case = OnboardingCaseRepository(db).get(tenant_id, case_id)
    if case is None:
        raise NotFoundError("Onboarding case not found.")
    return case


def list_case_steps(db: Session, tenant_id: uuid.UUID, case_id: uuid.UUID) -> list[OnboardingCaseStep]:
    return OnboardingCaseStepRepository(db).list_for_case(tenant_id, case_id)


def start_case(
    db: Session, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, template_id: uuid.UUID | None = None,
    name: str | None = None, created_by: uuid.UUID | None = None,
) -> OnboardingCase:
    """Creates a case and immediately instantiates its steps, spawning a
    real `Task` or `DocumentRequest` per step via the same cross-module
    call convention used throughout this codebase."""
    from app.modules.leads.repository import LeadRepository

    lead = LeadRepository(db).get(tenant_id, lead_id)
    if lead is None:
        raise NotFoundError("Lead not found.")

    template = None
    template_steps: list = []
    if template_id is not None:
        template = get_template_or_404(db, tenant_id, template_id)
        template_steps = list_template_steps(db, tenant_id, template_id)

    started_at = _utcnow()
    case = OnboardingCaseRepository(db).create(
        tenant_id=tenant_id, lead_id=lead_id, template_id=template_id,
        name=name or (template.name if template else "Onboarding"),
        status=OnboardingCaseStatus.IN_PROGRESS, started_at=started_at, created_by=created_by,
    )

    step_repo = OnboardingCaseStepRepository(db)
    for index, template_step in enumerate(template_steps):
        _instantiate_step(
            db, step_repo, tenant_id=tenant_id, lead_id=lead_id, case_id=case.id, sort_order=index,
            step_type=template_step.step_type, title=template_step.title, description=template_step.description,
            due_in_days=template_step.due_in_days, template_step_id=template_step.id, started_at=started_at,
            created_by=created_by,
        )

    if not template_steps:
        case.status = OnboardingCaseStatus.COMPLETED
        case.completed_at = _utcnow()
        db.add(case)
        db.flush()

    from app.modules.audit.service import log_event
    from app.modules.crm.service import record_activity

    log_event(db, tenant_id=tenant_id, actor_user_id=created_by, action="onboarding_case.started", entity_type="onboarding_case", entity_id=case.id)
    record_activity(
        db, tenant_id=tenant_id, lead_id=lead_id, actor_id=created_by,
        activity_type="onboarding_case.started", summary=f"Onboarding started: {case.name}",
    )
    return case


def _instantiate_step(
    db: Session, step_repo: OnboardingCaseStepRepository, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, case_id: uuid.UUID,
    sort_order: int, step_type: OnboardingStepType, title: str, description: str, due_in_days: int | None,
    template_step_id: uuid.UUID | None, started_at: datetime, created_by: uuid.UUID | None,
) -> OnboardingCaseStep:
    task_id = None
    document_request_id = None

    if step_type == OnboardingStepType.TASK:
        from app.modules.crm.service import create_task

        due_at = started_at + timedelta(days=due_in_days) if due_in_days is not None else None
        task = create_task(
            db, tenant_id=tenant_id, lead_id=lead_id, title=title, description=description,
            created_by=created_by, due_at=due_at, source="onboarding",
        )
        task_id = task.id
    elif step_type == OnboardingStepType.DOCUMENT_REQUEST:
        from app.modules.documents.service import create_request

        request = create_request(db, tenant_id=tenant_id, lead_id=lead_id, title=title, description=description, requested_by=created_by)
        document_request_id = request.id

    return step_repo.create(
        tenant_id=tenant_id, case_id=case_id, template_step_id=template_step_id, sort_order=sort_order, step_type=step_type,
        title=title, description=description, task_id=task_id, document_request_id=document_request_id,
    )


def cancel_case(db: Session, *, tenant_id: uuid.UUID, case: OnboardingCase, actor_id: uuid.UUID | None) -> OnboardingCase:
    if case.status in {OnboardingCaseStatus.COMPLETED, OnboardingCaseStatus.CANCELLED}:
        raise ValidationFailedError("This case is already finished.", code="case_already_finished")
    case.status = OnboardingCaseStatus.CANCELLED
    db.add(case)
    db.flush()

    from app.modules.audit.service import log_event

    log_event(db, tenant_id=tenant_id, actor_user_id=actor_id, action="onboarding_case.cancelled", entity_type="onboarding_case", entity_id=case.id)
    return case


def complete_step_manually(db: Session, *, tenant_id: uuid.UUID, case: OnboardingCase, step: OnboardingCaseStep, actor_id: uuid.UUID | None) -> OnboardingCaseStep:
    """For ad hoc steps with no underlying `Task`/`DocumentRequest` to
    drive completion. Steps backed by a real resource should be completed
    by finishing that resource (completing the task, approving the
    document) — see `advance_case_step_for_task`/`advance_case_step_for_document_request`."""
    if step.task_id is not None or step.document_request_id is not None:
        raise ValidationFailedError(
            "This step is tied to a task or document request — complete that instead.", code="step_not_manually_completable"
        )
    _complete_step(db, tenant_id=tenant_id, step=step)
    _maybe_complete_case(db, tenant_id=tenant_id, case_id=case.id)
    return step


def _complete_step(db: Session, *, tenant_id: uuid.UUID, step: OnboardingCaseStep) -> None:
    step.status = OnboardingCaseStepStatus.COMPLETED
    step.completed_at = _utcnow()
    db.add(step)
    db.flush()


def _maybe_complete_case(db: Session, *, tenant_id: uuid.UUID, case_id: uuid.UUID) -> None:
    case_repo = OnboardingCaseRepository(db)
    case = case_repo.get(tenant_id, case_id)
    if case is None or case.status != OnboardingCaseStatus.IN_PROGRESS:
        return
    steps = OnboardingCaseStepRepository(db).list_for_case(tenant_id, case_id)
    if steps and all(s.status != OnboardingCaseStepStatus.PENDING for s in steps):
        case.status = OnboardingCaseStatus.COMPLETED
        case.completed_at = _utcnow()
        db.add(case)
        db.flush()

        from app.modules.audit.service import log_event

        log_event(db, tenant_id=tenant_id, actor_user_id=None, action="onboarding_case.completed", entity_type="onboarding_case", entity_id=case.id)


def advance_case_step_for_task(db: Session, *, tenant_id: uuid.UUID, task_id: uuid.UUID) -> None:
    """Soft no-op if the task isn't tied to any onboarding case step — a
    plain manually-created task must never be blocked or altered by this
    hook. Called from `crm.service.complete_task`."""
    step = OnboardingCaseStepRepository(db).get_by_task_id(tenant_id, task_id)
    if step is None or step.status != OnboardingCaseStepStatus.PENDING:
        return
    _complete_step(db, tenant_id=tenant_id, step=step)
    _maybe_complete_case(db, tenant_id=tenant_id, case_id=step.case_id)


def advance_case_step_for_document_request(db: Session, *, tenant_id: uuid.UUID, document_request_id: uuid.UUID) -> None:
    """Soft no-op if the document request isn't tied to any onboarding
    case step. Called from `documents.service.approve_document_request`."""
    step = OnboardingCaseStepRepository(db).get_by_document_request_id(tenant_id, document_request_id)
    if step is None or step.status != OnboardingCaseStepStatus.PENDING:
        return
    _complete_step(db, tenant_id=tenant_id, step=step)
    _maybe_complete_case(db, tenant_id=tenant_id, case_id=step.case_id)
