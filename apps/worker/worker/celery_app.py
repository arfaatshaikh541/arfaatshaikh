"""Celery application entry point.

The worker imports and runs the exact same domain services as the API
(`app.modules.*`) rather than re-implementing business logic - `gridkeep-
worker` depends on `gridkeep-api` as a uv workspace member so both
processes share one source of truth.

Milestone 1 ships a single real, useful scheduled task
(`expire_stale_reservations` - see `worker.tasks`) tied to the credit-
ledger foundation. Campaign/enrichment/export/CRM tasks are Milestone 2+
work; the named queues below are declared now so the routing scheme is
fixed from the start, but only `queue.maintenance` is actually consumed
until those milestones land.
"""

from app.core.config import get_settings
from celery import Celery

settings = get_settings()

celery_app = Celery(
    "gridkeep",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue="queue.maintenance",
    task_routes={
        "worker.tasks.expire_stale_reservations": {"queue": "queue.maintenance"},
    },
)

from worker import beat_schedule  # noqa: E402

celery_app.conf.beat_schedule = beat_schedule.BEAT_SCHEDULE
