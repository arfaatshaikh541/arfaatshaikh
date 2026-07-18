"""Producer-side Celery client for the API.

`apps/worker` depends on `apps/api` (to reuse its domain services), so
the dependency can never point the other way - the API cannot import
`apps.worker.campaign_tasks.run_campaign_task` directly. Instead it
publishes tasks by registered name via `send_task`, exactly like any
external producer would; it never needs the task's implementation, only
its name and argument shape.
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

_celery_client = Celery(
    "gridkeep-api-client", broker=settings.celery_broker_url, backend=settings.celery_result_backend
)
_celery_client.conf.task_default_queue = "queue.maintenance"


def enqueue_campaign_task(task_id: str) -> None:
    _celery_client.send_task(
        "worker.campaign_tasks.run_campaign_task", args=[task_id], queue="queue.search"
    )


def enqueue_business_enrichment(enrichment_id: str) -> None:
    _celery_client.send_task(
        "worker.enrichment_tasks.run_business_enrichment",
        args=[enrichment_id],
        queue="queue.enrichment",
    )


def enqueue_export(export_id: str) -> None:
    _celery_client.send_task(
        "worker.export_tasks.run_export",
        args=[export_id],
        queue="queue.export",
    )
