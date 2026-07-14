import logging
from datetime import datetime, timedelta, timezone

from app.celery_app import celery_app
from app.core.db import session_scope, set_rls_context
from app.modules.communications.service import retry_failed_deliveries, send_task_reminders_for_tenant
from app.modules.tenancy.repository import TenantRepository

logger = logging.getLogger("worker.communications")

TASK_REMINDER_LOOKAHEAD_HOURS = 24


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@celery_app.task(name="app.tasks.communications.retry_email_deliveries", autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
def retry_email_deliveries() -> int:
    """Re-attempts every FAILED delivery (across all tenants) under the
    retry cap. `is_platform_admin=True` bypasses RLS for the whole sweep;
    `retry_failed_deliveries` itself only ever touches rows it selected
    via an explicit query, so no tenant boundary is actually crossed."""
    with session_scope() as db:
        set_rls_context(db, tenant_id=None, is_platform_admin=True)
        count = retry_failed_deliveries(db, tenant_id=None, max_attempts=3)
    logger.info("Retried %d failed email deliveries", count)
    return count


@celery_app.task(name="app.tasks.communications.send_task_reminders", autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
def send_task_reminders() -> int:
    """Thin per-tenant-loop wrapper around
    `communications.service.send_task_reminders_for_tenant` (unit-tested
    directly there against a real DB session)."""
    reminded = 0
    with session_scope() as db:
        set_rls_context(db, tenant_id=None, is_platform_admin=True)
        cutoff = _utcnow() + timedelta(hours=TASK_REMINDER_LOOKAHEAD_HOURS)
        for tenant in TenantRepository(db).list_all(limit=10000):
            reminded += send_task_reminders_for_tenant(db, tenant_id=tenant.id, before=cutoff)
    logger.info("Processed %d task reminders", reminded)
    return reminded
