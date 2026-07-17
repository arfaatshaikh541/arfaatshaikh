"""Celery tasks.

Milestone 1 ships one real task: expiring stale credit reservations. It
is a genuine, working task - not a placeholder - because the credit
ledger foundation (reserve/commit/release) is in scope for this
milestone even though nothing creates reservations yet outside of tests
(campaigns, which will, are Milestone 2).
"""

from app.core.db import AsyncSessionLocal
from app.core.logging import configure_logging, get_logger
from app.modules.usage.services import sweep_expired_reservations

from worker.async_utils import run_db_task
from worker.celery_app import celery_app

logger = get_logger("gridkeep.worker")


async def _sweep_expired_reservations_async() -> int:
    async with AsyncSessionLocal() as session:
        count = await sweep_expired_reservations(session)
        await session.commit()
        return count


@celery_app.task(name="worker.tasks.expire_stale_reservations")
def expire_stale_reservations() -> int:
    configure_logging()
    count = run_db_task(_sweep_expired_reservations_async())
    logger.info("reservation_sweep_complete", expired_count=count)
    return count
