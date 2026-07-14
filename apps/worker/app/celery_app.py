from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "cops_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.cleanup"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=60,
)

celery_app.conf.beat_schedule = {
    "cleanup-expired-sessions": {
        "task": "app.tasks.cleanup.cleanup_expired_sessions",
        "schedule": crontab(minute="*/15"),
    },
    "cleanup-expired-invitations": {
        "task": "app.tasks.cleanup.cleanup_expired_invitations",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "cleanup-expired-feature-overrides": {
        "task": "app.tasks.cleanup.cleanup_expired_feature_overrides",
        "schedule": crontab(minute=30, hour="*/6"),
    },
}
