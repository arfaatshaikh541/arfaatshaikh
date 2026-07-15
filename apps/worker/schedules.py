"""Celery Beat schedule. Milestone 1: maintenance sweeps only. Per-tenant-
integration sync frequency (Milestone 2) is data-driven from
`tenant_integrations`, not hardcoded here — a dynamic scheduler task will
enqueue individual sync jobs rather than Beat statically listing them."""

from __future__ import annotations

from celery.schedules import crontab

BEAT_SCHEDULE = {
    "cleanup-expired-sessions-daily": {
        "task": "worker.tasks.cleanup_expired_sessions",
        "schedule": crontab(hour=3, minute=0),
    },
    "expire-support-access-grants-every-5-minutes": {
        "task": "worker.tasks.expire_support_access_grants",
        "schedule": crontab(minute="*/5"),
    },
}
