"""Celery beat schedule for periodic maintenance tasks."""

BEAT_SCHEDULE = {
    "expire-stale-credit-reservations": {
        "task": "worker.tasks.expire_stale_reservations",
        "schedule": 300.0,  # every 5 minutes
    },
}
