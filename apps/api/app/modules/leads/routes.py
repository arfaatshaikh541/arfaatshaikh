import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.db import get_db, set_rls_context
from app.core.errors import NotFoundError
from app.core.pagination import Page, PageParams, build_page, paginate
from app.dependencies.entitlements import check_usage_limit, require_module
from app.dependencies.permissions import require_permission
from app.dependencies.tenant import get_tenant_context
from app.modules.leads import service as leads_service
from app.modules.leads.schemas import (
    AssignLeadRequest,
    CreateQualificationFormRequest,
    CreateQuestionRequest,
    CreateServiceRequest,
    LeadSummary,
    LeadUpdateRequest,
    ManualLeadCreateRequest,
    PublicLeadCaptureRequest,
    ReorderQuestionsRequest,
)
from app.modules.tenancy import service as tenancy_service

public_router = APIRouter(prefix="/public/capture", tags=["public-capture"])
router = APIRouter(prefix="/tenant/leads", tags=["leads"])
services_router = APIRouter(prefix="/tenant/services", tags=["services"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@public_router.get("/{token}/services")
def get_public_services(token: str, db: Session = Depends(get_db)) -> dict:
    tenant = tenancy_service.resolve_tenant_by_capture_token(db, token)
    if tenant is None:
        raise NotFoundError("Not found.")
    set_rls_context(db, tenant_id=tenant.id, is_platform_admin=False)
    services = leads_service.list_public_services(db, tenant.id)
    return {
        "tenant_name": tenant.name,
        "services": [{"id": str(s.id), "name": s.name, "description": s.description} for s in services],
    }


@public_router.get("/{token}/form")
def get_public_form(token: str, service_id: uuid.UUID | None = None, db: Session = Depends(get_db)) -> dict:
    tenant, form = leads_service.get_public_qualification_form(db, token, service_id)
    if form is None:
        return {"form_id": None, "questions": []}
    questions_with_options = leads_service.list_form_questions_with_options(db, tenant.id, form.id)
    return {
        "form_id": str(form.id),
        "questions": [
            {
                "id": str(item["question"].id),
                "label": item["question"].label,
                "question_type": item["question"].question_type.value,
                "is_required": item["question"].is_required,
                "sort_order": item["question"].sort_order,
                "options": [{"id": str(o.id), "label": o.label, "value": o.value} for o in item["options"]],
            }
            for item in questions_with_options
        ],
    }


@public_router.post("/{token}/enquiry", status_code=201)
def submit_public_enquiry(token: str, payload: PublicLeadCaptureRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    lead, is_duplicate = leads_service.capture_public_lead(db, token=token, ip_address=_client_ip(request), payload=payload)
    if lead is None:
        # Honeypot path — identical success shape, nothing was persisted.
        return {"status": "received"}
    return {"status": "received", "reference_number": lead.reference_number}


@router.get("", response_model=Page[LeadSummary])
def list_leads(
    stage_id: uuid.UUID | None = None, assigned_user_id: uuid.UUID | None = None, service_id: uuid.UUID | None = None,
    q: str | None = None, params: PageParams = Depends(),
    ctx: TenantContext = Depends(require_permission("leads.view")),
    _mod: TenantContext = Depends(require_module("crm")),
    db: Session = Depends(get_db),
) -> Page[LeadSummary]:
    from app.modules.leads.repository import LeadRepository

    stmt = LeadRepository(db).search(ctx.tenant_id, stage_id=stage_id, assigned_user_id=assigned_user_id, service_id=service_id, query=q)
    items, total = paginate(db, stmt, params)
    summaries = [
        LeadSummary(
            id=lead.id, reference_number=lead.reference_number, first_name=lead.first_name, last_name=lead.last_name,
            email=lead.email, phone=lead.phone, company=lead.company, service_id=lead.service_id, stage_id=lead.stage_id,
            priority=lead.priority, assigned_user_id=lead.assigned_user_id, is_possible_duplicate=lead.is_possible_duplicate,
            created_at=lead.created_at.isoformat(),
        )
        for lead in items
    ]
    return build_page(summaries, total, params)


@router.post("", status_code=201)
def create_lead(
    payload: ManualLeadCreateRequest,
    ctx: TenantContext = Depends(require_permission("leads.create")),
    _mod: TenantContext = Depends(require_module("lead_capture")),
    _usage: TenantContext = Depends(check_usage_limit("leads", feature_code="leads")),
    db: Session = Depends(get_db),
) -> dict:
    tenant = tenancy_service.get_tenant_or_404(db, ctx.tenant_id)
    lead = leads_service.create_manual_lead(db, tenant_id=ctx.tenant_id, tenant_slug=tenant.slug, created_by=ctx.user_id, payload=payload)
    return {"id": str(lead.id), "reference_number": lead.reference_number}


@router.get("/{lead_id}")
def get_lead(
    lead_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("leads.view")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> dict:
    lead = leads_service.get_lead_or_404(db, ctx.tenant_id, lead_id)
    return {
        "id": str(lead.id), "reference_number": lead.reference_number, "first_name": lead.first_name,
        "last_name": lead.last_name, "email": lead.email, "phone": lead.phone, "company": lead.company,
        "service_id": str(lead.service_id) if lead.service_id else None,
        "stage_id": str(lead.stage_id) if lead.stage_id else None,
        "pipeline_id": str(lead.pipeline_id) if lead.pipeline_id else None,
        "priority": lead.priority.value, "priority_locked": lead.priority_locked, "score": lead.score,
        "estimated_value": float(lead.estimated_value) if lead.estimated_value else None,
        "assigned_user_id": str(lead.assigned_user_id) if lead.assigned_user_id else None,
        "preferred_contact_method": lead.preferred_contact_method.value if lead.preferred_contact_method else None,
        "consent_status": lead.consent_status.value,
        "is_possible_duplicate": lead.is_possible_duplicate,
        "duplicate_of_lead_id": str(lead.duplicate_of_lead_id) if lead.duplicate_of_lead_id else None,
        "created_at": lead.created_at.isoformat(),
    }


@router.patch("/{lead_id}")
def update_lead(
    lead_id: uuid.UUID, payload: LeadUpdateRequest,
    ctx: TenantContext = Depends(require_permission("leads.update")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> dict:
    lead = leads_service.get_lead_or_404(db, ctx.tenant_id, lead_id)
    updates = payload.model_dump(exclude_unset=True, exclude={"next_follow_up_at"})
    if payload.next_follow_up_at is not None:
        from datetime import datetime

        updates["next_follow_up_at"] = datetime.fromisoformat(payload.next_follow_up_at)
    leads_service.update_lead(db, tenant_id=ctx.tenant_id, lead=lead, updates=updates, actor_id=ctx.user_id)
    return {"status": "ok"}


@router.post("/{lead_id}/assign")
def assign_lead(
    lead_id: uuid.UUID, payload: AssignLeadRequest,
    ctx: TenantContext = Depends(require_permission("leads.assign")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> dict:
    lead = leads_service.get_lead_or_404(db, ctx.tenant_id, lead_id)
    leads_service.assign_lead(db, tenant_id=ctx.tenant_id, lead=lead, assigned_user_id=payload.assigned_user_id, actor_id=ctx.user_id)
    return {"status": "ok"}


@services_router.get("")
def list_services(ctx: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> list[dict]:
    return [
        {"id": str(s.id), "name": s.name, "description": s.description, "is_active": s.is_active}
        for s in leads_service.list_services(db, ctx.tenant_id)
    ]


@services_router.post("", status_code=201)
def create_service(
    payload: CreateServiceRequest,
    ctx: TenantContext = Depends(require_permission("services.manage")), db: Session = Depends(get_db),
) -> dict:
    service = leads_service.create_service(
        db, tenant_id=ctx.tenant_id, name=payload.name, description=payload.description, category_id=payload.category_id
    )
    return {"id": str(service.id), "name": service.name}


qualification_forms_router = APIRouter(prefix="/tenant/qualification-forms", tags=["qualification-forms"])


@qualification_forms_router.get("")
def list_qualification_forms(ctx: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> list[dict]:
    return [
        {"id": str(f.id), "name": f.name, "service_id": str(f.service_id) if f.service_id else None, "is_active": f.is_active}
        for f in leads_service.list_qualification_forms(db, ctx.tenant_id)
    ]


@qualification_forms_router.post("", status_code=201)
def create_qualification_form(
    payload: CreateQualificationFormRequest,
    ctx: TenantContext = Depends(require_permission("services.manage")), db: Session = Depends(get_db),
) -> dict:
    form = leads_service.create_qualification_form(db, tenant_id=ctx.tenant_id, name=payload.name, service_id=payload.service_id)
    return {"id": str(form.id), "name": form.name}


@qualification_forms_router.get("/{form_id}/questions")
def list_questions(form_id: uuid.UUID, ctx: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> list[dict]:
    leads_service.get_qualification_form_or_404(db, ctx.tenant_id, form_id)
    items = leads_service.list_questions_with_options(db, ctx.tenant_id, form_id)
    return [
        {
            "id": str(item["question"].id), "label": item["question"].label,
            "question_type": item["question"].question_type.value, "is_required": item["question"].is_required,
            "sort_order": item["question"].sort_order, "maps_to_field": item["question"].maps_to_field,
            "options": [{"id": str(o.id), "label": o.label, "value": o.value} for o in item["options"]],
        }
        for item in items
    ]


@qualification_forms_router.post("/{form_id}/questions", status_code=201)
def add_question(
    form_id: uuid.UUID, payload: CreateQuestionRequest,
    ctx: TenantContext = Depends(require_permission("services.manage")), db: Session = Depends(get_db),
) -> dict:
    leads_service.get_qualification_form_or_404(db, ctx.tenant_id, form_id)
    question = leads_service.add_question(
        db, tenant_id=ctx.tenant_id, form_id=form_id, label=payload.label, question_type=payload.question_type,
        is_required=payload.is_required, maps_to_field=payload.maps_to_field, options=payload.options,
    )
    return {"id": str(question.id), "label": question.label}


@qualification_forms_router.put("/{form_id}/questions/reorder")
def reorder_questions(
    form_id: uuid.UUID, payload: ReorderQuestionsRequest,
    ctx: TenantContext = Depends(require_permission("services.manage")), db: Session = Depends(get_db),
) -> dict:
    leads_service.get_qualification_form_or_404(db, ctx.tenant_id, form_id)
    leads_service.reorder_questions(db, tenant_id=ctx.tenant_id, form_id=form_id, question_ids_in_order=payload.question_ids)
    return {"status": "ok"}
