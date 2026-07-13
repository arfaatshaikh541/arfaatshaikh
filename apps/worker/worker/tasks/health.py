from worker.celery_app import celery_app


@celery_app.task(name="worker.tasks.ping")
def ping() -> str:
    """Trivial liveness task, used by health checks and to verify the
    broker/worker wiring in local dev and CI."""
    return "pong"
