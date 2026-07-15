import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.db import get_db
from app.dependencies.entitlements import require_module
from app.dependencies.permissions import require_permission
from app.modules.onboarding import service as onboarding_service
from app.modules.onboarding.models import OnboardingCaseStatus
from app.modules.onboarding.schemas import CreateOnboardingTemplateRequest, StartOnboardingCaseRequest

templates_router = APIRouter(prefix="/tenant/onboarding-templates", tags=["onboarding-templates"])
router = APIRouter(prefix="/tenant/onboarding-cases", tags=["onboarding-cases"])


def _template_to_dict(db: Session, tenant_id: uuid.UUID, template) -> dict:
    steps = onboarding_service.list_template_steps(db, tenant_id, template.id)
    return {
        "id": str(template.id), "name": template.name, "description": template.description, "is_active": template.is_active,
        "steps": [
            {
                "id": str(s.id), "step_type": s.step_type.value, "title": s.title, "description": s.description,
                "due_in_days": s.due_in_days, "sort_order": s.sort_order,
            }
            for s in steps
        ],
    }


def _case_to_dict(db: Session, tenant_id: uuid.UUID, case) -> dict:
    steps = onboarding_service.list_case_steps(db, tenant_id, case.id)
    return {
        "id": str(case.id), "lead_id": str(case.lead_id), "template_id": str(case.template_id) if case.template_id else None,
        "name": case.name, "status": case.status.value,
        "started_at": case.started_at.isoformat() if case.started_at else None,
        "completed_at": case.completed_at.isoformat() if case.completed_at else None,
        "steps": [
            {
                "id": str(s.id), "step_type": s.step_type.value, "title": s.title, "description": s.description,
                "status": s.status.value, "task_id": str(s.task_id) if s.task_id else None,
                "document_request_id": str(s.document_request_id) if s.document_request_id else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None, "sort_order": s.sort_order,
            }
            for s in steps
        ],
    }


# --- Templates -------------------------------------------------------

@templates_router.get("")
def list_templates(
    ctx: TenantContext = Depends(require_permission("onboarding.view")),
    _mod: TenantContext = Depends(require_module("client_onboarding")), db: Session = Depends(get_db),
) -> list[dict]:
    return [_template_to_dict(db, ctx.tenant_id, t) for t in onboarding_service.list_templates(db, ctx.tenant_id)]


@templates_router.post("", status_code=201)
def create_template(
    payload: CreateOnboardingTemplateRequest, ctx: TenantContext = Depends(require_permission("onboarding.manage")),
    _mod: TenantContext = Depends(require_module("client_onboarding")), db: Session = Depends(get_db),
) -> dict:
    template = onboarding_service.create_template(
        db, tenant_id=ctx.tenant_id, name=payload.name, description=payload.description,
        steps=[s.model_dump() for s in payload.steps],
    )
    return _template_to_dict(db, ctx.tenant_id, template)


# --- Cases -------------------------------------------------------------

@router.get("")
def list_cases(
    lead_id: uuid.UUID | None = None, status: OnboardingCaseStatus | None = None,
    ctx: TenantContext = Depends(require_permission("onboarding.view")),
    _mod: TenantContext = Depends(require_module("client_onboarding")), db: Session = Depends(get_db),
) -> list[dict]:
    cases = (
        onboarding_service.list_cases_for_lead(db, ctx.tenant_id, lead_id) if lead_id
        else onboarding_service.list_cases_for_tenant(db, ctx.tenant_id, status=status)
    )
    return [_case_to_dict(db, ctx.tenant_id, c) for c in cases]


@router.post("", status_code=201)
def start_case(
    payload: StartOnboardingCaseRequest, ctx: TenantContext = Depends(require_permission("onboarding.manage")),
    _mod: TenantContext = Depends(require_module("client_onboarding")), db: Session = Depends(get_db),
) -> dict:
    case = onboarding_service.start_case(
        db, tenant_id=ctx.tenant_id, lead_id=payload.lead_id, template_id=payload.template_id,
        name=payload.name, created_by=ctx.user_id,
    )
    return _case_to_dict(db, ctx.tenant_id, case)


@router.get("/{case_id}")
def get_case(
    case_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("onboarding.view")),
    _mod: TenantContext = Depends(require_module("client_onboarding")), db: Session = Depends(get_db),
) -> dict:
    case = onboarding_service.get_case_or_404(db, ctx.tenant_id, case_id)
    return _case_to_dict(db, ctx.tenant_id, case)


@router.post("/{case_id}/cancel")
def cancel_case(
    case_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("onboarding.manage")),
    _mod: TenantContext = Depends(require_module("client_onboarding")), db: Session = Depends(get_db),
) -> dict:
    case = onboarding_service.get_case_or_404(db, ctx.tenant_id, case_id)
    case = onboarding_service.cancel_case(db, tenant_id=ctx.tenant_id, case=case, actor_id=ctx.user_id)
    return _case_to_dict(db, ctx.tenant_id, case)


@router.post("/{case_id}/steps/{step_id}/complete")
def complete_step(
    case_id: uuid.UUID, step_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("onboarding.manage")),
    _mod: TenantContext = Depends(require_module("client_onboarding")), db: Session = Depends(get_db),
) -> dict:
    case = onboarding_service.get_case_or_404(db, ctx.tenant_id, case_id)
    steps = {s.id: s for s in onboarding_service.list_case_steps(db, ctx.tenant_id, case_id)}
    step = steps.get(step_id)
    if step is None:
        from app.core.errors import NotFoundError

        raise NotFoundError("Onboarding case step not found.")
    onboarding_service.complete_step_manually(db, tenant_id=ctx.tenant_id, case=case, step=step, actor_id=ctx.user_id)
    case = onboarding_service.get_case_or_404(db, ctx.tenant_id, case_id)
    return _case_to_dict(db, ctx.tenant_id, case)
