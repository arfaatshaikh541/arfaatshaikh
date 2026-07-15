"""The Milestone 3/4 companion to `professional_services_template.py`:
default scoring rules, one round-robin assignment rule, default
appointment types and staff availability, and the email templates for
every automated trigger event — applied to every newly created tenant so
scoring/assignment/communications/booking aren't empty out of the box.
Ordinary tenant-owned configuration data — fully editable afterward via
the relevant module's API, not special-cased application logic.
"""
import uuid
from datetime import time

from sqlalchemy.orm import Session

MERGE_FIELD_HELP = (
    "Available merge fields: {{first_name}}, {{last_name}}, {{company}}, {{reference_number}}, "
    "{{tenant_name}}, {{stage_name}}, {{assigned_user_name}}, {{task_title}}, {{task_due_date}}, "
    "{{staff_name}}, {{appointment_type_name}}, {{appointment_date}}, {{appointment_time}}, {{location}}, "
    "{{proposal_title}}, {{proposal_total}}, {{proposal_link}}, "
    "{{document_title}}, {{document_link}}, "
    "{{deadline_title}}, {{deadline_due_date}}"
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
    template_repo.create(
        tenant_id=tenant_id, name="Appointment Booked", trigger_event=EmailTriggerEvent.APPOINTMENT_BOOKED,
        subject="Appointment confirmed: {{appointment_date}} at {{appointment_time}}",
        body_text=(
            "Hi {{first_name}},\n\nYour {{appointment_type_name}} with {{staff_name}} is confirmed for "
            "{{appointment_date}} at {{appointment_time}} ({{location}}).\n\n— {{tenant_name}}"
        ),
    )
    template_repo.create(
        tenant_id=tenant_id, name="Appointment Reminder", trigger_event=EmailTriggerEvent.APPOINTMENT_REMINDER,
        subject="Reminder: your appointment is on {{appointment_date}}",
        body_text=(
            "Hi {{first_name}},\n\nThis is a reminder of your {{appointment_type_name}} with {{staff_name}} on "
            "{{appointment_date}} at {{appointment_time}} ({{location}}).\n\n— {{tenant_name}}"
        ),
    )
    template_repo.create(
        tenant_id=tenant_id, name="Appointment Cancelled", trigger_event=EmailTriggerEvent.APPOINTMENT_CANCELLED,
        subject="Your appointment on {{appointment_date}} has been cancelled",
        body_text="Hi {{first_name}},\n\nYour {{appointment_type_name}} on {{appointment_date}} has been cancelled.\n\n— {{tenant_name}}",
    )
    template_repo.create(
        tenant_id=tenant_id, name="Proposal Sent", trigger_event=EmailTriggerEvent.PROPOSAL_SENT,
        subject="Your proposal from {{tenant_name}}: {{proposal_title}}",
        body_text=(
            "Hi {{first_name}},\n\nPlease find your proposal '{{proposal_title}}' ({{proposal_total}}) attached. "
            "Review and respond here: {{proposal_link}}\n\n— {{tenant_name}}"
        ),
    )
    template_repo.create(
        tenant_id=tenant_id, name="Proposal Accepted", trigger_event=EmailTriggerEvent.PROPOSAL_ACCEPTED,
        subject="Thank you for accepting: {{proposal_title}}",
        body_text="Hi {{first_name}},\n\nThank you for accepting our proposal '{{proposal_title}}'. We'll be in touch shortly.\n\n— {{tenant_name}}",
    )
    template_repo.create(
        tenant_id=tenant_id, name="Proposal Rejected", trigger_event=EmailTriggerEvent.PROPOSAL_REJECTED,
        subject="Regarding your proposal: {{proposal_title}}",
        body_text="Hi {{first_name}},\n\nWe noted that '{{proposal_title}}' was declined. Please reach out if you'd like to discuss further.\n\n— {{tenant_name}}",
    )
    template_repo.create(
        tenant_id=tenant_id, name="Document Requested", trigger_event=EmailTriggerEvent.DOCUMENT_REQUESTED,
        subject="Document needed: {{document_title}}",
        body_text=(
            "Hi {{first_name}},\n\nWe need the following from you: {{document_title}}. "
            "Please upload it here: {{document_link}}\n\n— {{tenant_name}}"
        ),
    )
    template_repo.create(
        tenant_id=tenant_id, name="Document Approved", trigger_event=EmailTriggerEvent.DOCUMENT_APPROVED,
        subject="Received: {{document_title}}",
        body_text="Hi {{first_name}},\n\nThank you — we've received and approved '{{document_title}}'.\n\n— {{tenant_name}}",
    )
    template_repo.create(
        tenant_id=tenant_id, name="Document Rejected", trigger_event=EmailTriggerEvent.DOCUMENT_REJECTED,
        subject="Action needed: {{document_title}}",
        body_text=(
            "Hi {{first_name}},\n\nWe weren't able to accept the '{{document_title}}' you uploaded. "
            "Please upload a new copy here: {{document_link}}\n\n— {{tenant_name}}"
        ),
    )
    template_repo.create(
        tenant_id=tenant_id, name="Deadline Reminder", trigger_event=EmailTriggerEvent.DEADLINE_UPCOMING,
        subject="Upcoming deadline: {{deadline_title}}",
        body_text="Hi {{first_name}},\n\nA reminder that '{{deadline_title}}' is due on {{deadline_due_date}}.\n\n— {{tenant_name}}",
    )

    from app.modules.booking import service as booking_service

    booking_service.create_appointment_type(
        db, tenant_id=tenant_id, name="Free Consultation", description="A 30-minute introductory consultation.", duration_minutes=30
    )
    booking_service.create_appointment_type(db, tenant_id=tenant_id, name="Callback", description="A 15-minute callback.", duration_minutes=15)

    if owner_user_id:
        weekday_hours = [
            {"day_of_week": day, "start_time": time(9, 0), "end_time": time(17, 0)}
            for day in range(5)  # Monday-Friday
        ]
        booking_service.set_weekly_availability(db, tenant_id, owner_user_id, windows=weekday_hours)

    from app.modules.workflow_automation import service as workflow_service
    from app.modules.workflow_automation.models import WorkflowActionType, WorkflowTriggerEvent

    welcome_workflow = workflow_service.create_workflow(
        db, tenant_id=tenant_id, name="New Lead Welcome Sequence", description="Tags every new lead, then reminds staff to follow up if it hasn't moved.",
        trigger_event=WorkflowTriggerEvent.LEAD_CREATED, trigger_config={}, conditions=[],
    )
    workflow_service.add_step(
        db, tenant_id=tenant_id, workflow_id=welcome_workflow.id, delay_minutes=0,
        action_type=WorkflowActionType.ADD_TAG, action_config={"tag_name": "New Lead"},
    )
    workflow_service.add_step(
        db, tenant_id=tenant_id, workflow_id=welcome_workflow.id, delay_minutes=24 * 60,
        action_type=WorkflowActionType.CREATE_TASK,
        action_config={"title": "Follow up if no contact made", "description": "Auto-created by the New Lead Welcome Sequence workflow.", "due_in_hours": 4},
    )

    from app.modules.proposals import service as proposals_service

    proposals_service.create_template(
        db, tenant_id=tenant_id, name="Standard Engagement Proposal",
        description="Default line items for a typical professional-services engagement.",
        terms="This proposal is valid for 30 days from the date of issue. Fees are quoted in AED and exclude any government filing fees unless stated otherwise.",
        line_items=[
            {"description": "Initial consultation and needs assessment", "quantity": 1, "unit_price": 500},
            {"description": "Engagement setup and documentation", "quantity": 1, "unit_price": 1500},
        ],
    )

    from app.modules.onboarding import service as onboarding_service
    from app.modules.onboarding.models import OnboardingStepType

    onboarding_service.create_template(
        db, tenant_id=tenant_id, name="Standard Client Onboarding",
        description="The default checklist for a newly engaged client.",
        steps=[
            {
                "step_type": OnboardingStepType.DOCUMENT_REQUEST, "title": "Passport / Emirates ID copy",
                "description": "A clear copy of the client's passport or Emirates ID.",
            },
            {
                "step_type": OnboardingStepType.TASK, "title": "Welcome call",
                "description": "Call the client to walk through next steps.", "due_in_days": 2,
            },
        ],
    )
