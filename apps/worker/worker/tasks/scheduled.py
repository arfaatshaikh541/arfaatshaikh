"""Periodic follow-up automation (Module 9 / Module 10).

Both tasks are idempotent: they check what's already been sent/notified
before acting, so re-running on a tight beat schedule never spams the
same alert twice. See docs/architecture/erd-summary-m3.md.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.db.base import utcnow
from app.db.session import SessionLocal
from app.models.appointment import Appointment
from app.models.lead import Lead
from app.repositories.communication import MessageLogRepository, NotificationRepository
from app.repositories.lead import LeadRepository
from app.repositories.membership import MembershipRepository
from app.repositories.task import TaskFilters, TaskRepository
from app.repositories.tenant import TenantRepository
from app.services.email_service import EmailMessage, send_email_safely
from app.services.message_template_service import MessageTemplateService
from worker.celery_app import celery_app


@celery_app.task(name="worker.tasks.escalate_overdue_tasks")
def escalate_overdue_tasks() -> int:
    """Create a one-time in-app notification for a task's assignee the
    first time it's observed overdue. Dedupe is by scanning the
    assignee's existing notifications for one already pointing at this
    task, rather than a stored "escalated" flag on the task itself."""
    db = SessionLocal()
    escalated = 0
    try:
        tenants = TenantRepository(db).list_all(limit=1000)
        tasks_repo = TaskRepository(db)
        memberships = MembershipRepository(db)
        notifications = NotificationRepository(db)

        for tenant in tenants:
            overdue = tasks_repo.list_for_tenant(
                tenant.id, filters=TaskFilters(overdue_only=True), page=1, page_size=500
            )
            for task in overdue.items:
                if task.assigned_membership_id is None:
                    continue
                membership = memberships.get_by_id_for_tenant(
                    tenant.id, task.assigned_membership_id
                )
                if membership is None:
                    continue
                existing = notifications.list_for_user(tenant.id, membership.user_id, limit=200)
                if any(
                    n.related_entity_type == "task" and n.related_entity_id == str(task.id)
                    for n in existing
                ):
                    continue
                notifications.create(
                    tenant_id=tenant.id,
                    user_id=membership.user_id,
                    title="Task overdue",
                    body=task.title,
                    related_entity_type="task",
                    related_entity_id=str(task.id),
                )
                escalated += 1
        db.commit()
        return escalated
    finally:
        db.close()


@celery_app.task(name="worker.tasks.send_follow_up_reminders")
def send_follow_up_reminders() -> int:
    """Email the tenant's "follow_up" template to a lead once its
    next_follow_up_at has passed. Dedupe is by checking the append-only
    MessageLog for a follow_up entry sent to this lead in the last 24
    hours, so a 15-minute beat schedule doesn't resend the same reminder
    on every tick; a lead overdue for more than a day gets nudged again."""
    db = SessionLocal()
    sent = 0
    recent_cutoff = utcnow() - timedelta(hours=24)
    try:
        tenants = TenantRepository(db).list_all(limit=1000)
        templates = MessageTemplateService(db)
        message_logs = MessageLogRepository(db)

        for tenant in tenants:
            stmt = select(Lead).where(
                Lead.tenant_id == tenant.id,
                Lead.next_follow_up_at.is_not(None),
                Lead.next_follow_up_at <= utcnow(),
                Lead.email.is_not(None),
            )
            due_leads = list(db.execute(stmt).scalars().all())
            if not due_leads:
                continue

            recent_logs = message_logs.list_for_tenant(tenant.id, limit=1000)
            recently_sent_lead_ids = {
                log.lead_id
                for log in recent_logs
                if log.template_key == "follow_up" and log.created_at >= recent_cutoff
            }

            for lead in due_leads:
                if lead.id in recently_sent_lead_ids or not lead.email:
                    continue
                rendered = templates.render(
                    tenant.id,
                    "follow_up",
                    {"first_name": lead.first_name, "tenant_name": tenant.name},
                )
                if rendered is None:
                    continue
                status = "sent"
                error_message = None
                try:
                    send_email_safely(
                        EmailMessage(
                            to=lead.email, subject=rendered.subject, text_body=rendered.body
                        )
                    )
                except Exception as exc:  # noqa: BLE001 - log and continue with the next lead
                    status = "failed"
                    error_message = str(exc)
                message_logs.record(
                    tenant_id=tenant.id,
                    template_key="follow_up",
                    channel="email",
                    recipient=lead.email,
                    status=status,
                    lead_id=lead.id,
                    error_message=error_message,
                )
                sent += 1
        db.commit()
        return sent
    finally:
        db.close()


@celery_app.task(name="worker.tasks.send_appointment_reminders")
def send_appointment_reminders() -> int:
    """Email the tenant's "appointment_reminder" template roughly 24 hours
    before each upcoming scheduled/confirmed appointment. Dedupe reuses
    the same 24h MessageLog window as send_follow_up_reminders; since
    MessageLog has no appointment_id column, dedupe is per-lead rather
    than per-appointment - a documented limitation for a lead with two
    appointments in the same reminder window. See
    docs/architecture/erd-summary-m4.md."""
    db = SessionLocal()
    sent = 0
    now = utcnow()
    window_start = now + timedelta(hours=23)
    window_end = now + timedelta(hours=25)
    recent_cutoff = now - timedelta(hours=24)
    try:
        tenants = TenantRepository(db).list_all(limit=1000)
        templates = MessageTemplateService(db)
        message_logs = MessageLogRepository(db)
        leads_repo = LeadRepository(db)

        for tenant in tenants:
            stmt = select(Appointment).where(
                Appointment.tenant_id == tenant.id,
                Appointment.status.in_(("scheduled", "confirmed")),
                Appointment.starts_at >= window_start,
                Appointment.starts_at < window_end,
            )
            upcoming = list(db.execute(stmt).scalars().all())
            if not upcoming:
                continue

            recent_logs = message_logs.list_for_tenant(tenant.id, limit=1000)
            recently_sent_lead_ids = {
                log.lead_id
                for log in recent_logs
                if log.template_key == "appointment_reminder" and log.created_at >= recent_cutoff
            }

            for appointment in upcoming:
                if appointment.lead_id in recently_sent_lead_ids:
                    continue
                lead = leads_repo.get_by_id_for_tenant(tenant.id, appointment.lead_id)
                if lead is None or not lead.email:
                    continue
                rendered = templates.render(
                    tenant.id,
                    "appointment_reminder",
                    {
                        "first_name": lead.first_name,
                        "tenant_name": tenant.name,
                        "appointment_time": appointment.starts_at.isoformat(),
                    },
                )
                if rendered is None:
                    continue
                status = "sent"
                error_message = None
                try:
                    send_email_safely(
                        EmailMessage(
                            to=lead.email, subject=rendered.subject, text_body=rendered.body
                        )
                    )
                except Exception as exc:  # noqa: BLE001 - log and continue with the next lead
                    status = "failed"
                    error_message = str(exc)
                message_logs.record(
                    tenant_id=tenant.id,
                    template_key="appointment_reminder",
                    channel="email",
                    recipient=lead.email,
                    status=status,
                    lead_id=lead.id,
                    error_message=error_message,
                )
                sent += 1
                recently_sent_lead_ids.add(lead.id)
        db.commit()
        return sent
    finally:
        db.close()
