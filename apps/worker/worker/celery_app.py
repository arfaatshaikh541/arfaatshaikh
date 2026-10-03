from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "world_of_islam",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    imports=("worker.tasks",),
    beat_schedule_filename="/tmp/celerybeat-schedule",
    beat_schedule={
        "send-email-outbox": {"task": "woi.email.send_outbox", "schedule": 60.0},
        "purge-expired": {"task": "woi.auth.purge_expired", "schedule": crontab(hour=3, minute=17)},
        "validate-data": {"task": "woi.data.validate", "schedule": crontab(hour=3, minute=41)},
    },
)
