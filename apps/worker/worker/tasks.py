"""Celery tasks. Thin wrappers: the work is in app/services/background.py (tested without Celery).

task                       input  output (JSON dict)                           retry                                   idempotent because
woi.email.send_outbox      none   {status, sent, failed, expired}             5x, backoff 30s..15min + jitter on a    a row is marked sent/failed in its own
                                                                              mail-server outage                      transaction; sent rows are never selected
woi.auth.purge_expired     none   {status, deleted: {table: n}}               3x, backoff 60s                         deletes only rows past the retention cut-off
woi.data.validate          none   {status, checks, failed: {check: n}}        no automatic retry (a failed check is   writes one audit row per run; no data changes
                                                                              a finding, not a fault)
"""
from __future__ import annotations

import asyncio
import logging

from app.core.config import get_settings
from app.db.session import Database
from app.services import background
from worker.celery_app import celery_app

log = logging.getLogger("woi.worker")


def _run(job):
    """Run `job(session, settings)` on a fresh engine (a prefork child must not share the parent's connections)."""
    async def go():
        settings = get_settings()
        db = Database(settings)
        try:
            async with db.session_factory() as session:
                return await job(session, settings)
        finally:
            await db.dispose()
    return asyncio.run(go())


@celery_app.task(name="woi.email.send_outbox", bind=True, autoretry_for=(background.TransientEmailError,),
                 retry_backoff=30, retry_backoff_max=900, retry_jitter=True, max_retries=5, soft_time_limit=120, time_limit=180)
def send_email_outbox(self) -> dict:
    return _run(lambda session, settings: background.send_email_outbox(session, settings))


@celery_app.task(name="woi.auth.purge_expired", bind=True, autoretry_for=(OSError,), retry_backoff=60, max_retries=3, soft_time_limit=300, time_limit=360)
def purge_expired(self) -> dict:
    return _run(lambda session, settings: background.purge_expired(session))


@celery_app.task(name="woi.data.validate", bind=True, soft_time_limit=1200, time_limit=1500)  # about 150 s on the populated database (measured)
def validate_data(self) -> dict:
    return _run(lambda session, settings: background.run_data_validation(session))
