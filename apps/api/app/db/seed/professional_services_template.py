"""The "Professional Services" default template: services and a default
qualification form, applied to every newly created tenant (platform-admin
tenant creation calls `apply_professional_services_template` directly —
see `app.modules.platform_admin.service.create_tenant_with_owner`) as
well as to the seeded demo tenant.

This is ordinary tenant-owned configuration data — fully editable and
reorderable by tenant administrators after creation via the
services/qualification-forms API, not special-cased application logic.
"""
from sqlalchemy.orm import Session

DEFAULT_SERVICES: list[dict] = [
    {"name": "External Audit", "description": "Independent statutory audit of financial statements."},
    {"name": "Internal Audit", "description": "Internal controls and process assurance review."},
    {"name": "Corporate Tax", "description": "UAE corporate tax registration, filing, and advisory."},
    {"name": "VAT", "description": "VAT registration, filing, and compliance."},
    {"name": "Accounting and Bookkeeping", "description": "Ongoing bookkeeping and management accounts."},
    {"name": "Financial Advisory", "description": "Financial due diligence and advisory services."},
    {"name": "Business Setup", "description": "Mainland, Free Zone, and Offshore company formation."},
    {"name": "Company Liquidation", "description": "Voluntary liquidation and deregistration support."},
    {"name": "Compliance Consultation", "description": "Regulatory and compliance advisory."},
]

EMIRATES = ["Abu Dhabi", "Dubai", "Sharjah", "Ajman", "Umm Al Quwain", "Ras Al Khaimah", "Fujairah"]
REVENUE_RANGES = ["Under AED 1M", "AED 1M - 5M", "AED 5M - 20M", "AED 20M - 50M", "Over AED 50M"]
BUDGET_RANGES = ["Under AED 10,000", "AED 10,000 - 25,000", "AED 25,000 - 50,000", "Over AED 50,000"]

# label, question_type, is_required, maps_to_field, options
DEFAULT_QUESTIONS: list[dict] = [
    {
        "label": "Which service do you require?", "question_type": "single_select", "is_required": True,
        "maps_to_field": "service_id", "options": [s["name"] for s in DEFAULT_SERVICES],
    },
    {
        "label": "What is your company name?", "question_type": "short_text", "is_required": False,
        "maps_to_field": "company", "options": [],
    },
    {
        "label": "Is your company Mainland, Free Zone or Offshore?", "question_type": "single_select",
        "is_required": True, "maps_to_field": None, "options": ["Mainland", "Free Zone", "Offshore"],
    },
    {
        "label": "In which emirate is it registered?", "question_type": "single_select", "is_required": True,
        "maps_to_field": None, "options": EMIRATES,
    },
    {
        "label": "What is the approximate annual revenue range?", "question_type": "single_select",
        "is_required": False, "maps_to_field": None, "options": REVENUE_RANGES,
    },
    {
        "label": "What is your deadline?", "question_type": "date", "is_required": False,
        "maps_to_field": None, "options": [],
    },
    {
        "label": "What is your expected budget range?", "question_type": "single_select", "is_required": False,
        "maps_to_field": None, "options": BUDGET_RANGES,
    },
    {
        "label": "What is your preferred contact method?", "question_type": "single_select", "is_required": True,
        "maps_to_field": "preferred_contact_method", "options": ["Email", "Phone", "WhatsApp"],
    },
    {
        "label": "Would you like to book a consultation?", "question_type": "yes_no", "is_required": False,
        "maps_to_field": None, "options": [],
    },
]


def apply_professional_services_template(db: Session, tenant_id) -> None:
    from app.modules.crm.service import ensure_default_pipeline
    from app.modules.leads import service as leads_service
    from app.modules.leads.models import QualificationQuestionType
    from app.modules.leads.repository import ServiceRepository

    ensure_default_pipeline(db, tenant_id)

    service_repo = ServiceRepository(db)
    if service_repo.list_for_tenant(tenant_id):
        return  # already templated (idempotent — never duplicate on re-run)

    for index, service_def in enumerate(DEFAULT_SERVICES):
        service_repo.create(tenant_id=tenant_id, name=service_def["name"], description=service_def["description"], sort_order=index)

    form = leads_service.create_qualification_form(db, tenant_id=tenant_id, name="Default Enquiry Form")
    for question_def in DEFAULT_QUESTIONS:
        leads_service.add_question(
            db, tenant_id=tenant_id, form_id=form.id, label=question_def["label"],
            question_type=QualificationQuestionType(question_def["question_type"]),
            is_required=question_def["is_required"], maps_to_field=question_def["maps_to_field"],
            options=question_def["options"],
        )
