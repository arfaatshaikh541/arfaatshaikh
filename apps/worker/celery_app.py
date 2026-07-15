"""GRIDKEEP Celery worker entrypoint.

Milestone 1 scope: infrastructure + two real maintenance tasks (expired-
session cleanup, expired support-access-grant sweep) that prove the queue/
schedule/task pipeline end-to-end. Milestone 2+ adds the substantive
workload — connector sync, event ingestion, correlation, action execution,
report generation — each in its own queue (see QUEUE_* below, matching
architecture §21).

Reuses apps/api's `core`/`db`/`modules` packages directly via a sys.path
insert rather than a separately-packaged shared library. This is a known
Milestone 1 simplification — extracting the shared domain code into an
installable package (e.g. `packages/gridkeep-core`) is tracked as a
post-M1 housekeeping item in docs/project-status.md, not hidden here.
"""

from __future__ import annotations

import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[1] / "api"
sys.path.insert(0, str(_API_ROOT))

from celery import Celery  # noqa: E402

from core.config import settings  # noqa: E402

QUEUE_SYNC = "sync"
QUEUE_INGEST = "ingest"
QUEUE_CORRELATE = "correlate"
QUEUE_ACTIONS = "actions"
QUEUE_REPORTS = "reports"
QUEUE_DEFAULT = "default"

celery_app = Celery("gridkeep", broker=settings.redis_url, backend=settings.redis_url)

celery_app.conf.update(
    task_default_queue=QUEUE_DEFAULT,
    task_routes={
        "worker.tasks.cleanup_expired_sessions": {"queue": QUEUE_DEFAULT},
        "worker.tasks.expire_support_access_grants": {"queue": QUEUE_DEFAULT},
    },
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    timezone="UTC",
    enable_utc=True,
)

celery_app.autodiscover_tasks(["worker"], related_name="tasks")

from worker import schedules as _schedules  # noqa: E402

celery_app.conf.beat_schedule = _schedules.BEAT_SCHEDULE
