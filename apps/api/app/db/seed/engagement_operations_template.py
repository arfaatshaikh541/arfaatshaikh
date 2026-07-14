"""The Milestone 3 companion to `professional_services_template.py`:
default scoring rules, one round-robin assignment rule, and three email
templates, applied to every newly created tenant so scoring/assignment/
communications aren't empty out of the box. Ordinary tenant-owned
configuration data — fully editable afterward via the scoring/assignment/
communications APIs, not special-cased application logic.
"""
import uuid

from sqlalchemy.orm import Session

MERGE_FIELD_HELP = (
    "Available merge fields: {{first_name}}, {{last_name}}, {{company}}, {{reference_number}}, "
    "{{tenant_name}}, {{stage_name}}, {{assigned_user_name}}, {{task_title}}, {{task_due_date}}"
)


def apply_engagement_operations_template(
    db: Session, tenant_id, *, question_ids_by_label: dict[str, uuid.UUID], owner_user_id: uuid.UUID | None = None
) -> None:
    from app.modules.communications.models import EmailTriggerEvent
    from app.modules.communications.repository import EmailTemplateRepository
    from app.modules.scoring import service as scoring_service
    from app.modules.scoring.models import ScoringOperator
    from app.modules.scoring.repository import ScoringRuleRepository

    if ScoringRuleRepository(db).list_for_tenant(tenant_id):
        return  # already templated (idempotent — never duplicate on re-run)

    scoring_service.ensure_scoring_settings(db, tenant_id)

    consultation_question_id = question_ids_by_label.get("Would you like to book a consultation?")
    budget_question_id = question_ids_by_label.get("What is your expected budget range?")

    if consultation_question_id is not None:
        scoring_service.create_rule(
            db, tenant_id=tenant_id, name="Requested a consultation", field=f"answer:{consultation_question_id}",
            operator=ScoringOperator.EQUALS, value="Yes", points=30,
        )
    if budget_question_id is not None:
        scoring_service.create_rule(
            db, tenant_id=tenant_id, name="High budget range", field=f"answer:{budget_question_id}",
            operator=ScoringOperator.EQUALS, value="Over AED 50,000", points=25,
        )
    scoring_service.create_rule(
        db, tenant_id=tenant_id, name="Consent given", field="consent_status",
        operator=ScoringOperator.EQUALS, value="given", points=20,
    )
    scoring_service.create_rule(
        db, tenant_id=tenant_id, name="Company name provided", field="company",
        operator=ScoringOperator.IS_SET, value=None, points=10,
    )

    from app.modules.assignment import service as assignment_service
    from app.modules.assignment.models import AssignmentStrategy

    assignment_service.create_rule(
        db, tenant_id=tenant_id, name="Round-robin new leads", strategy=AssignmentStrategy.ROUND_ROBIN,
        conditions={}, eligible_user_ids=[owner_user_id] if owner_user_id else [],
    )

    template_repo = EmailTemplateRepository(db)
    template_repo.create(
        tenant_id=tenant_id, name="Lead Assigned Notification", trigger_event=EmailTriggerEvent.LEAD_ASSIGNED,
        subject="New lead assigned: {{first_name}} {{last_name}}",
        body_text=(
            "You have been assigned a new lead.\n\n"
            "Name: {{first_name}} {{last_name}}\nCompany: {{company}}\nReference: {{reference_number}}\n\n"
            f"— {{{{tenant_name}}}}\n\n{MERGE_FIELD_HELP}"
        ),
    )
    template_repo.create(
        tenant_id=tenant_id, name="Deal Won", trigger_event=EmailTriggerEvent.STAGE_CHANGED, trigger_stage_outcome="won",
        subject="Welcome aboard, {{first_name}}!",
        body_text=(
            "Hi {{first_name}},\n\nThank you for choosing {{tenant_name}}. "
            "We're excited to get started on {{reference_number}}.\n\n— {{tenant_name}}"
        ),
    )
    template_repo.create(
        tenant_id=tenant_id, name="Task Reminder", trigger_event=EmailTriggerEvent.TASK_REMINDER,
        subject="Reminder: {{task_title}}",
        body_text=f"This is a reminder that '{{{{task_title}}}}' is due {{{{task_due_date}}}}.\n\n— {{{{tenant_name}}}}\n\n{MERGE_FIELD_HELP}",
    )
