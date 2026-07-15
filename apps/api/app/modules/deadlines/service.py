import uuid
from datetime import UTC, datetime, timedelta
from datetime import date as date_

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.modules.deadlines.models import Deadline, DeadlineStatus
from app.modules.deadlines.repository import DeadlineRepository

REMINDER_LEAD_DAYS = 7


def _utcnow() -> datetime:
    return datetime.now(UTC)


def create_deadline(
    db: Session, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, title: str, description: str = "",
    due_date: date_, recurrence_interval_days: int | None = None, created_by: uuid.UUID | None = None,
) -> Deadline:
    from app.modules.leads.repository import LeadRepository

    lead = LeadRepository(db).get(tenant_id, lead_id)
    if lead is None:
        raise NotFoundError("Lead not found.")

    deadline = DeadlineRepository(db).create(
        tenant_id=tenant_id, lead_id=lead_id, title=title, description=description, due_date=due_date,
        recurrence_interval_days=recurrence_interval_days, created_by=created_by,
    )

    from app.modules.audit.service import log_event
    from app.modules.crm.service import record_activity

    log_event(db, tenant_id=tenant_id, actor_user_id=created_by, action="deadline.created", entity_type="deadline", entity_id=deadline.id)
    record_activity(
        db, tenant_id=tenant_id, lead_id=lead_id, actor_id=created_by,
        activity_type="deadline.created", summary=f"Deadline added: {title} (due {due_date.isoformat()})",
    )
    return deadline


def get_deadline_or_404(db: Session, tenant_id: uuid.UUID, deadline_id: uuid.UUID) -> Deadline:
    deadline = DeadlineRepository(db).get(tenant_id, deadline_id)
    if deadline is None:
        raise NotFoundError("Deadline not found.")
    return deadline


def list_deadlines_for_lead(db: Session, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> list[Deadline]:
    return DeadlineRepository(db).list_for_lead(tenant_id, lead_id)


def list_deadlines_for_tenant(db: Session, tenant_id: uuid.UUID, *, status: DeadlineStatus | None = None) -> list[Deadline]:
    return DeadlineRepository(db).list_for_tenant(tenant_id, status=status)


def complete_deadline(db: Session, *, tenant_id: uuid.UUID, deadline: Deadline, actor_id: uuid.UUID | None) -> Deadline:
    if deadline.status != DeadlineStatus.OPEN:
        raise ValidationFailedError("This deadline is already completed.", code="deadline_already_completed")

    deadline.status = DeadlineStatus.COMPLETED
    deadline.completed_at = _utcnow()
    db.add(deadline)
    db.flush()

    from app.modules.audit.service import log_event
    from app.modules.crm.service import record_activity

    log_event(db, tenant_id=tenant_id, actor_user_id=actor_id, action="deadline.completed", entity_type="deadline", entity_id=deadline.id)
    record_activity(
        db, tenant_id=tenant_id, lead_id=deadline.lead_id, actor_id=actor_id,
        activity_type="deadline.completed", summary=f"Deadline completed: {deadline.title}",
    )

    if deadline.recurrence_interval_days:
        next_due_date = deadline.due_date + timedelta(days=deadline.recurrence_interval_days)
        create_deadline(
            db, tenant_id=tenant_id, lead_id=deadline.lead_id, title=deadline.title, description=deadline.description,
            due_date=next_due_date, recurrence_interval_days=deadline.recurrence_interval_days, created_by=actor_id,
        )
    return deadline


def _default_context(deadline: Deadline, lead, tenant) -> dict:
    return {
        "first_name": lead.first_name if lead else "",
        "last_name": lead.last_name if lead else "",
        "reference_number": lead.reference_number if lead else "",
        "tenant_name": tenant.name if tenant else "",
        "deadline_title": deadline.title,
        "deadline_due_date": deadline.due_date.isoformat(),
    }


def send_deadline_reminders_for_tenant(db: Session, *, tenant_id: uuid.UUID, on_or_before: date_) -> int:
    from app.modules.leads.repository import LeadRepository
    from app.modules.tenancy.repository import TenantRepository

    tenant = TenantRepository(db).get(tenant_id)
    if tenant is None:
        return 0

    lead_repo = LeadRepository(db)
    reminded = 0
    for deadline in DeadlineRepository(db).list_due_for_reminder(tenant_id=tenant_id, on_or_before=on_or_before):
        lead = lead_repo.get(tenant_id, deadline.lead_id)
        if lead is not None and lead.email:
            from app.modules.communications.models import EmailTriggerEvent
            from app.modules.communications.service import send_templated_email

            sent = send_templated_email(
                db, tenant_id=tenant_id, trigger_event=EmailTriggerEvent.DEADLINE_UPCOMING, recipient=lead.email,
                lead_id=deadline.lead_id, context=_default_context(deadline, lead, tenant),
            )
            if sent is not None:
                reminded += 1
        deadline.reminder_sent_at = _utcnow()
        db.add(deadline)
    return reminded
