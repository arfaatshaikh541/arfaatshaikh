"""Periodic maintenance: deletes the underlying object storage file for
every completed export whose retention period (`settings.export_
retention_days`, set on completion - see `worker.export_tasks`) has
passed. Mirrors `worker.tasks.expire_stale_reservations`'s shape exactly:
a thin Celery wrapper around a cross-tenant service function that does
the real work under `set_platform_bypass`.
"""

from app.core.db import AsyncSessionLocal
from app.core.logging import configure_logging, get_logger
from app.modules.exports.services import cleanup_expired_exports

from worker.async_utils import run_db_task
from worker.celery_app import celery_app

logger = get_logger("gridkeep.worker.export_cleanup")


async def _cleanup_expired_exports_async() -> int:
    async with AsyncSessionLocal() as session:
        count = await cleanup_expired_exports(session)
        await session.commit()
        return count


@celery_app.task(name="worker.export_cleanup_tasks.cleanup_expired_exports")
def cleanup_expired_exports_task() -> int:
    configure_logging()
    count = run_db_task(_cleanup_expired_exports_async())
    logger.info("export_cleanup_sweep_complete", deleted_count=count)
    return count
