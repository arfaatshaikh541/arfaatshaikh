import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.db import set_rls_context
from app.core.email import send_lead_acknowledgement_email
from app.core.errors import NotFoundError, RateLimitedError
from app.core.rate_limit import is_rate_limited
from app.modules.audit.service import log_event
from app.modules.entitlements import service as entitlements_service
from app.modules.leads.models import ConsentStatus, Lead, QualificationForm
from app.modules.leads.repository import (
    LeadRepository,
    LeadSourceRepository,
    QualificationAnswerRepository,
    QualificationFormRepository,
    QualificationOptionRepository,
    QualificationQuestionRepository,
    ServiceCategoryRepository,
    ServiceRepository,
)
from app.modules.tenancy import service as tenancy_service
from app.modules.tenancy.models import Tenant

DUPLICATE_WINDOW = timedelta(days=30)
CAPTURE_THROTTLE_MAX_ATTEMPTS = 10
CAPTURE_THROTTLE_WINDOW_SECONDS = 10 * 60
DEFAULT_SOURCE_CODE = "website"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def generate_reference_number(tenant_slug: str) -> str:
    prefix = "".join(ch for ch in tenant_slug.upper() if ch.isalnum())[:4] or "LEAD"
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def get_public_qualification_form(db: Session, token: str, service_id: uuid.UUID | None) -> tuple[Tenant, QualificationForm | None]:
    tenant = tenancy_service.resolve_tenant_by_capture_token(db, token)
    if tenant is None:
        raise NotFoundError("Not found.")
    set_rls_context(db, tenant_id=tenant.id, is_platform_admin=False)
    form = QualificationFormRepository(db).get_for_service(tenant.id, service_id)
    return tenant, form


def list_public_services(db: Session, tenant_id: uuid.UUID) -> list:
    return ServiceRepository(db).list_for_tenant(tenant_id, active_only=True)


def list_form_questions_with_options(db: Session, tenant_id: uuid.UUID, form_id: uuid.UUID) -> list[dict]:
    question_repo = QualificationQuestionRepository(db)
    option_repo = QualificationOptionRepository(db)
    questions = question_repo.list_for_form(tenant_id, form_id)
    return [{"question": q, "options": option_repo.list_for_question(q.id)} for q in questions]


def capture_public_lead(
    db: Session, *, token: str, ip_address: str, payload,
) -> tuple[Lead | None, bool]:
    """Returns (lead_or_none, is_duplicate). `lead` is None only when the
    honeypot field was filled in — the caller must respond with the same
    generic success body either way, so a bot cannot distinguish
    "silently dropped" from "actually captured"."""
    tenant = tenancy_service.resolve_tenant_by_capture_token(db, token)
    if tenant is None:
        raise NotFoundError("Not found.")

    throttle_key = f"throttle:capture:{tenant.id}:{ip_address}"
    limited, retry_after = is_rate_limited(
        throttle_key, max_attempts=CAPTURE_THROTTLE_MAX_ATTEMPTS, window_seconds=CAPTURE_THROTTLE_WINDOW_SECONDS
    )
    if limited:
        raise RateLimitedError(f"Too many submissions. Try again in {retry_after} seconds.", code="capture_rate_limited")

    if payload.website:
        # Honeypot triggered — report success without persisting anything.
        return None, False

    set_rls_context(db, tenant_id=tenant.id, is_platform_admin=False)
    entitlements_service.assert_module_enabled(db, tenant.id, "lead_capture")

    lead_repo = LeadRepository(db)

    if payload.idempotency_key:
        existing = lead_repo.get_by_idempotency_key(tenant.id, payload.idempotency_key)
        if existing is not None:
            return existing, existing.is_possible_duplicate

    entitlements_service.check_and_increment_usage(db, tenant.id, metric_code="leads", feature_code="leads")

    duplicate = lead_repo.find_possible_duplicate(tenant.id, email=payload.email, phone=payload.phone, within=DUPLICATE_WINDOW)

    source_repo = LeadSourceRepository(db)
    source = source_repo.get_by_code(tenant.id, DEFAULT_SOURCE_CODE)
    if source is None:
        source = source_repo.create(tenant_id=tenant.id, code=DEFAULT_SOURCE_CODE, name="Website")

    from app.modules.crm.service import ensure_default_pipeline, record_activity

    pipeline, first_stage = ensure_default_pipeline(db, tenant.id)

    lead = lead_repo.create(
        tenant_id=tenant.id,
        reference_number=generate_reference_number(tenant.slug),
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        phone=payload.phone,
        company=payload.company,
        service_id=payload.service_id,
        source_id=source.id,
        pipeline_id=pipeline.id if pipeline else None,
        stage_id=first_stage.id if first_stage else None,
        preferred_contact_method=payload.preferred_contact_method,
        consent_status=ConsentStatus.GIVEN if payload.consent_given else ConsentStatus.PENDING,
        utm_source=payload.utm_source,
        utm_medium=payload.utm_medium,
        utm_campaign=payload.utm_campaign,
        submitted_ip=ip_address,
        idempotency_key=payload.idempotency_key,
        is_possible_duplicate=duplicate is not None,
        duplicate_of_lead_id=duplicate.id if duplicate else None,
    )

    answer_repo = QualificationAnswerRepository(db)
    question_repo = QualificationQuestionRepository(db)
    for answer_input in payload.answers:
        question = question_repo.get(tenant.id, answer_input.question_id)
        if question is None:
            continue
        answer_repo.create(
            tenant_id=tenant.id, lead_id=lead.id, question_id=question.id,
            question_label=question.label, answer_value={"value": answer_input.value}, created_at=_utcnow(),
        )

    record_activity(db, tenant_id=tenant.id, lead_id=lead.id, actor_id=None, activity_type="lead.created", summary="Lead captured from public enquiry form")
    if duplicate is not None:
        record_activity(
            db, tenant_id=tenant.id, lead_id=lead.id, actor_id=None, activity_type="lead.possible_duplicate",
            summary=f"Flagged as a possible duplicate of {duplicate.reference_number}",
        )

    from app.modules.crm.service import create_task

    create_task(
        db, tenant_id=tenant.id, lead_id=lead.id, title=f"Follow up with {lead.first_name} {lead.last_name}".strip(),
        description="Auto-created follow-up for a new enquiry.", assigned_user_id=None, created_by=None,
        due_at=_utcnow() + timedelta(hours=24), source="system",
    )

    if lead.email:
        send_lead_acknowledgement_email(to=lead.email, tenant_name=tenant.name, first_name=lead.first_name, reference_number=lead.reference_number)

    log_event(
        db, tenant_id=tenant.id, actor_user_id=None, action="lead.captured", entity_type="lead", entity_id=lead.id,
        after={"reference_number": lead.reference_number, "source": "public_capture"},
    )
    return lead, duplicate is not None


def create_manual_lead(db: Session, *, tenant_id: uuid.UUID, tenant_slug: str, created_by: uuid.UUID | None, payload) -> Lead:
    """Does NOT check/increment the "leads" usage limit itself — the
    `POST /tenant/leads` route already enforces that via the
    `check_usage_limit` dependency (the single source of truth for this
    metric on the authenticated path). Called directly by seed scripts
    too, which intentionally bypass usage enforcement for fixture data."""
    from app.modules.crm.service import ensure_default_pipeline, record_activity

    pipeline, first_stage = ensure_default_pipeline(db, tenant_id)
    lead_repo = LeadRepository(db)
    duplicate = lead_repo.find_possible_duplicate(tenant_id, email=payload.email, phone=payload.phone, within=DUPLICATE_WINDOW)

    lead = lead_repo.create(
        tenant_id=tenant_id,
        reference_number=generate_reference_number(tenant_slug),
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        phone=payload.phone,
        company=payload.company,
        service_id=payload.service_id,
        source_id=payload.source_id,
        pipeline_id=pipeline.id if pipeline else None,
        stage_id=first_stage.id if first_stage else None,
        preferred_contact_method=payload.preferred_contact_method,
        priority=payload.priority,
        estimated_value=payload.estimated_value,
        is_possible_duplicate=duplicate is not None,
        duplicate_of_lead_id=duplicate.id if duplicate else None,
    )
    record_activity(db, tenant_id=tenant_id, lead_id=lead.id, actor_id=created_by, activity_type="lead.created", summary="Lead created manually")
    log_event(db, tenant_id=tenant_id, actor_user_id=created_by, action="lead.created", entity_type="lead", entity_id=lead.id)
    return lead


def get_lead_or_404(db: Session, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> Lead:
    lead = LeadRepository(db).get(tenant_id, lead_id)
    if lead is None:
        raise NotFoundError("Lead not found.")
    return lead


def update_lead(db: Session, *, tenant_id: uuid.UUID, lead: Lead, updates: dict, actor_id: uuid.UUID | None) -> Lead:
    for field, value in updates.items():
        if value is not None:
            setattr(lead, field, value)
    db.add(lead)
    db.flush()
    from app.modules.crm.service import record_activity

    record_activity(db, tenant_id=tenant_id, lead_id=lead.id, actor_id=actor_id, activity_type="lead.updated", summary="Lead details updated")
    return lead


def assign_lead(db: Session, *, tenant_id: uuid.UUID, lead: Lead, assigned_user_id: uuid.UUID | None, actor_id: uuid.UUID | None) -> Lead:
    lead.assigned_user_id = assigned_user_id
    db.add(lead)
    db.flush()
    from app.modules.crm.service import record_activity

    summary = "Lead unassigned" if assigned_user_id is None else "Lead assigned"
    record_activity(db, tenant_id=tenant_id, lead_id=lead.id, actor_id=actor_id, activity_type="lead.assigned", summary=summary)
    log_event(db, tenant_id=tenant_id, actor_user_id=actor_id, action="lead.assigned", entity_type="lead", entity_id=lead.id)
    return lead


def list_services(db: Session, tenant_id: uuid.UUID):
    return ServiceRepository(db).list_for_tenant(tenant_id)


def create_service(db: Session, *, tenant_id: uuid.UUID, name: str, description: str = "", category_id: uuid.UUID | None = None):
    return ServiceRepository(db).create(tenant_id=tenant_id, name=name, description=description, category_id=category_id)


def list_service_categories(db: Session, tenant_id: uuid.UUID):
    return ServiceCategoryRepository(db).list_for_tenant(tenant_id)


def list_qualification_forms(db: Session, tenant_id: uuid.UUID):
    return QualificationFormRepository(db).list_for_tenant(tenant_id)


def get_qualification_form_or_404(db: Session, tenant_id: uuid.UUID, form_id: uuid.UUID) -> QualificationForm:
    form = QualificationFormRepository(db).get(tenant_id, form_id)
    if form is None:
        raise NotFoundError("Qualification form not found.")
    return form


def create_qualification_form(db: Session, *, tenant_id: uuid.UUID, name: str, service_id: uuid.UUID | None = None) -> QualificationForm:
    return QualificationFormRepository(db).create(tenant_id=tenant_id, name=name, service_id=service_id)


def list_questions_with_options(db: Session, tenant_id: uuid.UUID, form_id: uuid.UUID):
    return list_form_questions_with_options(db, tenant_id, form_id)


def add_question(
    db: Session, *, tenant_id: uuid.UUID, form_id: uuid.UUID, label: str, question_type, is_required: bool,
    maps_to_field: str | None, options: list[str],
):
    question_repo = QualificationQuestionRepository(db)
    existing = question_repo.list_for_form(tenant_id, form_id)
    question = question_repo.create(
        tenant_id=tenant_id, form_id=form_id, label=label, question_type=question_type,
        is_required=is_required, sort_order=len(existing), maps_to_field=maps_to_field,
    )
    option_repo = QualificationOptionRepository(db)
    for index, option_label in enumerate(options):
        option_repo.create(tenant_id=tenant_id, question_id=question.id, label=option_label, value=option_label, sort_order=index)
    return question


def reorder_questions(db: Session, *, tenant_id: uuid.UUID, form_id: uuid.UUID, question_ids_in_order: list[uuid.UUID]) -> None:
    question_repo = QualificationQuestionRepository(db)
    existing = {q.id: q for q in question_repo.list_for_form(tenant_id, form_id)}
    ordered = [existing[qid] for qid in question_ids_in_order if qid in existing]
    question_repo.reorder(ordered)
