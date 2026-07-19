"""Celery beat schedule for periodic maintenance tasks."""

BEAT_SCHEDULE = {
    "expire-stale-credit-reservations": {
        "task": "worker.tasks.expire_stale_reservations",
        "schedule": 300.0,  # every 5 minutes
    },
    "cleanup-expired-exports": {
        "task": "worker.export_cleanup_tasks.cleanup_expired_exports",
        "schedule": 3600.0,  # every hour - storage cleanup is not time-sensitive
    },
}
