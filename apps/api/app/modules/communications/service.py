import re
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.email import get_email_provider
from app.core.errors import NotFoundError, UsageLimitExceededError
from app.modules.communications.models import EmailDeliveryLog, EmailDeliveryStatus, EmailTemplate, EmailTriggerEvent
from app.modules.communications.repository import EmailDeliveryLogRepository, EmailTemplateRepository
from app.modules.entitlements import service as entitlements_service

_MERGE_FIELD_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def render_template(text: str, context: dict) -> str:
    """Whitelisted `{{field}}` substitution — never a template engine with
    code-execution capability (appsec: avoids SSTI). Unknown keys are left
    as literal `{{field}}` text rather than raising, so a template author's
    typo doesn't crash a send."""

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        if key in context and context[key] is not None:
            return str(context[key])
        return match.group(0)

    return _MERGE_FIELD_PATTERN.sub(_replace, text)


def list_templates(db: Session, tenant_id: uuid.UUID) -> list[EmailTemplate]:
    return EmailTemplateRepository(db).list_for_tenant(tenant_id)


def get_template_or_404(db: Session, tenant_id: uuid.UUID, template_id: uuid.UUID) -> EmailTemplate:
    template = EmailTemplateRepository(db).get(tenant_id, template_id)
    if template is None:
        raise NotFoundError("Email template not found.")
    return template


def create_template(
    db: Session, *, tenant_id: uuid.UUID, name: str, trigger_event: EmailTriggerEvent, subject: str, body_text: str,
    body_html: str | None = None, trigger_stage_outcome: str | None = None,
) -> EmailTemplate:
    return EmailTemplateRepository(db).create(
        tenant_id=tenant_id, name=name, trigger_event=trigger_event, subject=subject, body_text=body_text,
        body_html=body_html, trigger_stage_outcome=trigger_stage_outcome,
    )


def update_template(db: Session, *, tenant_id: uuid.UUID, template: EmailTemplate, updates: dict) -> EmailTemplate:
    for field, value in updates.items():
        if value is not None:
            setattr(template, field, value)
    db.add(template)
    db.flush()
    return template


def list_delivery_logs(
    db: Session, tenant_id: uuid.UUID, *, lead_id: uuid.UUID | None = None, status=None
) -> list[EmailDeliveryLog]:
    return EmailDeliveryLogRepository(db).list_for_tenant(tenant_id, lead_id=lead_id, status=status)


def _dispatch(
    db: Session, *, tenant_id: uuid.UUID, template_id: uuid.UUID | None, recipient: str, subject: str,
    body_text: str, body_html: str | None, lead_id: uuid.UUID | None,
) -> EmailDeliveryLog:
    log = EmailDeliveryLogRepository(db).create(
        tenant_id=tenant_id, template_id=template_id, lead_id=lead_id, recipient=recipient, subject=subject,
        body_text=body_text, body_html=body_html, created_at=_utcnow(),
    )
    log.attempt_count += 1
    try:
        get_email_provider().send(to=recipient, subject=subject, text_body=body_text, html_body=body_html)
        log.status = EmailDeliveryStatus.SENT
        log.sent_at = _utcnow()
        log.last_error = None
    except Exception as exc:  # noqa: BLE001 — delivery failures are expected and must not crash the caller
        log.status = EmailDeliveryStatus.FAILED
        log.last_error = str(exc)[:2000]
    db.add(log)
    db.flush()
    return log


def send_templated_email(
    db: Session, *, tenant_id: uuid.UUID, trigger_event: EmailTriggerEvent, recipient: str, context: dict,
    lead_id: uuid.UUID | None = None, stage_outcome: str | None = None,
) -> EmailDeliveryLog | None:
    """Soft-fails at every step (module disabled, no matching template,
    usage limit exceeded) by returning None rather than raising — a
    notification is never allowed to block the core CRUD action (lead
    creation, stage change) that triggered it."""
    entitlements = entitlements_service.resolve_entitlements(db, tenant_id)
    if not entitlements.module_enabled("communications"):
        return None

    template = EmailTemplateRepository(db).get_active_by_trigger(tenant_id, trigger_event, stage_outcome=stage_outcome)
    if template is None:
        return None

    try:
        entitlements_service.check_and_increment_usage(db, tenant_id, metric_code="messages", feature_code="messages")
    except UsageLimitExceededError:
        return None

    subject = render_template(template.subject, context)
    body_text = render_template(template.body_text, context)
    body_html = render_template(template.body_html, context) if template.body_html else None
    return _dispatch(
        db, tenant_id=tenant_id, template_id=template.id, recipient=recipient, subject=subject,
        body_text=body_text, body_html=body_html, lead_id=lead_id,
    )


def send_test_email(db: Session, *, tenant_id: uuid.UUID, template: EmailTemplate, recipient: str) -> EmailDeliveryLog:
    """Always sends regardless of module/usage state — a test send targets
    only the requesting admin's own email and must work even while
    configuring a not-yet-enabled communications setup."""
    sample_context = {
        "first_name": "Sample", "last_name": "Lead", "company": "Sample Co", "reference_number": "SAMPLE-0001",
        "tenant_name": "Your Tenant", "stage_name": "Qualified", "assigned_user_name": "Team Member",
        "task_title": "Sample task", "task_due_date": _utcnow().date().isoformat(),
    }
    subject = f"[TEST] {render_template(template.subject, sample_context)}"
    body_text = render_template(template.body_text, sample_context)
    body_html = render_template(template.body_html, sample_context) if template.body_html else None
    return _dispatch(
        db, tenant_id=tenant_id, template_id=template.id, recipient=recipient, subject=subject,
        body_text=body_text, body_html=body_html, lead_id=None,
    )


def retry_failed_deliveries(db: Session, *, tenant_id: uuid.UUID | None = None, max_attempts: int = 3) -> int:
    """Re-attempts every FAILED delivery under `max_attempts`, resending
    the exact rendered snapshot captured at the original send time. Called
    directly (unit-testable against a real DB + FakeEmailProvider) and by
    the Celery beat schedule (`apps/worker/app/tasks/communications.py`)."""
    logs = EmailDeliveryLogRepository(db).list_failed_for_retry(tenant_id, max_attempts=max_attempts)
    retried = 0
    for log in logs:
        log.attempt_count += 1
        try:
            get_email_provider().send(to=log.recipient, subject=log.subject, text_body=log.body_text, html_body=log.body_html)
            log.status = EmailDeliveryStatus.SENT
            log.sent_at = _utcnow()
            log.last_error = None
        except Exception as exc:  # noqa: BLE001
            log.status = EmailDeliveryStatus.FAILED
            log.last_error = str(exc)[:2000]
        db.add(log)
        retried += 1
    return retried


def send_task_reminders_for_tenant(db: Session, *, tenant_id: uuid.UUID, before: datetime) -> int:
    """Finds this tenant's open tasks due at/before `before` with no
    reminder sent yet, sends the active `task_reminder` template to each
    assignee, and marks `reminder_sent_at` — idempotent regardless of
    whether a template existed to send. Directly unit-testable against a
    real DB session; the Celery beat task
    (`apps/worker/app/tasks/communications.py`) is a thin per-tenant-loop
    wrapper around this."""
    from app.modules.crm.repository import TaskRepository
    from app.modules.identity.repository import UserRepository
    from app.modules.tenancy.repository import TenantRepository

    tenant = TenantRepository(db).get(tenant_id)
    if tenant is None:
        return 0

    task_repo = TaskRepository(db)
    user_repo = UserRepository(db)
    reminded = 0
    for task in task_repo.list_due_for_reminder(before=before, tenant_id=tenant_id):
        if task.assigned_user_id is not None:
            user = user_repo.get_by_id(task.assigned_user_id)
            if user is not None:
                sent = send_templated_email(
                    db, tenant_id=tenant_id, trigger_event=EmailTriggerEvent.TASK_REMINDER, recipient=user.email,
                    lead_id=task.lead_id,
                    context={
                        "task_title": task.title,
                        "task_due_date": task.due_at.isoformat() if task.due_at else "",
                        "tenant_name": tenant.name,
                    },
                )
                if sent is not None:
                    reminded += 1
        task.reminder_sent_at = _utcnow()
        db.add(task)
    return reminded
