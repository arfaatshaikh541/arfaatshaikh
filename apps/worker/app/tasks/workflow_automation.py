import logging
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.core.db import session_scope, set_rls_context
from app.modules.tenancy.repository import TenantRepository
from app.modules.workflow_automation.service import process_due_steps_for_tenant

logger = logging.getLogger("worker.workflow_automation")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@celery_app.task(name="app.tasks.workflow_automation.process_due_steps", autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
def process_due_steps() -> int:
    """Thin per-tenant-loop wrapper around
    `workflow_automation.service.process_due_steps_for_tenant`
    (unit-tested directly there against a real DB session), mirroring the
    Milestone 3/4 reminder sweeps exactly."""
    processed = 0
    with session_scope() as db:
        set_rls_context(db, tenant_id=None, is_platform_admin=True)
        now = _utcnow()
        for tenant in TenantRepository(db).list_all(limit=10000):
            processed += process_due_steps_for_tenant(db, tenant_id=tenant.id, before=now)
    logger.info("Processed %d due workflow steps", processed)
    return processed
