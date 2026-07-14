import logging
from datetime import datetime, timedelta, timezone

from app.celery_app import celery_app
from app.core.db import session_scope, set_rls_context
from app.modules.booking.service import send_appointment_reminders_for_tenant
from app.modules.tenancy.repository import TenantRepository

logger = logging.getLogger("worker.booking")

APPOINTMENT_REMINDER_LOOKAHEAD_HOURS = 24


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@celery_app.task(name="app.tasks.booking.send_appointment_reminders", autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
def send_appointment_reminders() -> int:
    """Thin per-tenant-loop wrapper around
    `booking.service.send_appointment_reminders_for_tenant` (unit-tested
    directly there against a real DB session), mirroring the Milestone 3
    task-reminder sweep."""
    reminded = 0
    with session_scope() as db:
        set_rls_context(db, tenant_id=None, is_platform_admin=True)
        cutoff = _utcnow() + timedelta(hours=APPOINTMENT_REMINDER_LOOKAHEAD_HOURS)
        for tenant in TenantRepository(db).list_all(limit=10000):
            reminded += send_appointment_reminders_for_tenant(db, tenant_id=tenant.id, before=cutoff)
    logger.info("Processed %d appointment reminders", reminded)
    return reminded
