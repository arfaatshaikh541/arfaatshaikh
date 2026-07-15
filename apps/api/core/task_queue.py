"""Lightweight Celery *client* for enqueuing tasks from the API process.

Deliberately does not import anything from `apps/worker` — enqueuing only
needs a task name and a broker connection; the worker process owns the
actual task registration. This keeps the API -> worker dependency
one-directional (the worker already depends on the API's core/db/modules;
the API must never depend back on the worker)."""

from __future__ import annotations

from celery import Celery

from core.config import settings

_client = Celery("gridkeep_api_client", broker=settings.redis_url)


def enqueue_integration_sync(tenant_id: str, tenant_integration_id: str, sync_run_id: str) -> str:
    result = _client.send_task(
        "worker.tasks.run_integration_sync",
        args=[tenant_id, tenant_integration_id, sync_run_id],
        queue="sync",
    )
    return result.id


def enqueue_run_correlation(tenant_id: str) -> str:
    result = _client.send_task("worker.tasks.run_correlation", args=[tenant_id], queue="correlate")
    return result.id
