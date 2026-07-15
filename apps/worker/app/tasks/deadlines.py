import logging
from datetime import datetime, timedelta, timezone

from app.celery_app import celery_app
from app.core.db import session_scope, set_rls_context
from app.modules.deadlines.service import REMINDER_LEAD_DAYS, send_deadline_reminders_for_tenant
from app.modules.tenancy.repository import TenantRepository

logger = logging.getLogger("worker.deadlines")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@celery_app.task(name="app.tasks.deadlines.send_deadline_reminders", autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
def send_deadline_reminders() -> int:
    """Thin per-tenant-loop wrapper around
    `deadlines.service.send_deadline_reminders_for_tenant`. Deadlines are
    date-granularity (not time-of-day), so this runs once daily rather
    than on the 15-minute cadence used for appointment/task reminders."""
    reminded = 0
    with session_scope() as db:
        set_rls_context(db, tenant_id=None, is_platform_admin=True)
        cutoff = (_utcnow() + timedelta(days=REMINDER_LEAD_DAYS)).date()
        for tenant in TenantRepository(db).list_all(limit=10000):
            reminded += send_deadline_reminders_for_tenant(db, tenant_id=tenant.id, on_or_before=cutoff)
    logger.info("Processed %d deadline reminders", reminded)
    return reminded
