from celery import Celery

from app.core.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "leadflow",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
    include=["worker.tasks.email", "worker.tasks.health"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_max_tasks_per_child=200,
)
