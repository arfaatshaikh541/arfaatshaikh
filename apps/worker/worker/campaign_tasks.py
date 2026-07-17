"""The campaign task-execution chain.

`run_campaign_task` processes exactly one page of a campaign's search:
- Idempotent: `lock_task_for_processing` only proceeds if the task is
  still `pending` - a duplicate Celery delivery (at-least-once delivery
  is normal) for an already-succeeded/already-running task is a no-op.
- Concurrency-limited: acquires a per-tenant Redis slot before touching
  the connector or the DB-status-changing work; if none is free, retries
  later without ever marking the task anything but `pending`.
- Retries transient/rate-limit connector errors with backoff; auth/quota/
  permanent errors fail the task immediately (no point retrying them).
- Checks for `pausing`/`cancelling` on the *parent campaign* right after
  claiming the task (before doing any connector work) and, on `pausing`/
  `cancelling`, finalizes the campaign instead of running the page - this
  is what makes pause/cancel prompt rather than waiting for the whole
  campaign to finish.
- On success, either enqueues the next page's task or finalizes the
  campaign as completed, reconciling the credit reservation to the
  *actual* number of businesses found (see docs/adr/0004).
"""

import os
import socket
import uuid
from datetime import UTC, datetime

from app.core.db import AsyncSessionLocal, set_platform_bypass, set_tenant_context
from app.core.logging import configure_logging, get_logger
from app.modules.campaign_jobs import repositories as jobs_repo
from app.modules.campaign_jobs.concurrency import acquire_tenant_slot, release_tenant_slot
from app.modules.campaigns import repositories as campaigns_repo
from app.modules.campaigns import state_machine
from app.modules.campaigns.services import build_search_query
from app.modules.usage.services import commit_reservation
from celery.exceptions import MaxRetriesExceededError
from connector_sdk import (
    ConnectorAuthError,
    ConnectorPermanentError,
    ConnectorQuotaError,
    ConnectorRateLimitError,
    ConnectorTransientError,
)
from connector_sdk.registry import get_connector

from worker.async_utils import run_db_task
from worker.celery_app import celery_app

logger = get_logger("gridkeep.worker.campaigns")

_WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"


class _SlotUnavailable(Exception):
    """Raised internally when no per-tenant concurrency slot is free.
    Caught by the Celery task wrapper, which retries without having
    touched the task's DB status at all."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _finalize_completed(session, campaign, job) -> None:
    job.status = "completed"
    job.completed_at = _utcnow()
    total_found = await jobs_repo.sum_succeeded_businesses_for_job(session, job.id)
    if campaign.reservation_id:
        await commit_reservation(
            session, reservation_id=campaign.reservation_id, actual_amount=float(total_found)
        )
    await state_machine.transition(
        session, campaign, to_status="completed", message="All pages processed"
    )


async def _finalize_paused(session, campaign, job) -> None:
    job.status = "paused"
    await state_machine.transition(
        session, campaign, to_status="paused", message="Paused between pages"
    )


async def _finalize_cancelled(session, campaign, job) -> None:
    job.status = "cancelled"
    total_found = await jobs_repo.sum_succeeded_businesses_for_job(session, job.id)
    if campaign.reservation_id:
        if total_found > 0:
            await commit_reservation(
                session, reservation_id=campaign.reservation_id, actual_amount=float(total_found)
            )
        else:
            from app.modules.usage.services import release_reservation

            await release_reservation(session, reservation_id=campaign.reservation_id)
    await state_machine.transition(
        session, campaign, to_status="cancelled", message="Cancelled between pages"
    )


async def _finalize_failed(
    session, campaign, job, *, error_type: str, message: str, task_id: uuid.UUID
) -> None:
    job.status = "failed"
    await campaigns_repo.record_error(
        session,
        tenant_id=campaign.tenant_id,
        campaign_id=campaign.id,
        task_id=task_id,
        error_type=error_type,
        message=message,
    )
    total_found = await jobs_repo.sum_succeeded_businesses_for_job(session, job.id)
    if campaign.reservation_id:
        if total_found > 0:
            await commit_reservation(
                session, reservation_id=campaign.reservation_id, actual_amount=float(total_found)
            )
        else:
            from app.modules.usage.services import release_reservation

            await release_reservation(session, reservation_id=campaign.reservation_id)
    to_status = "partially_completed" if total_found > 0 else "failed"
    await state_machine.transition(
        session, campaign, to_status=to_status, message=f"Task failed: {message}"
    )


async def _run_campaign_task_async(task_id_str: str) -> None:
    task_id = uuid.UUID(task_id_str)

    async with AsyncSessionLocal() as session:
        # campaign_tasks is RLS-protected and tenant_id is exactly what
        # this lookup is trying to discover, so - like the invitation-
        # accept-by-token and support-access-grant-by-id lookups in
        # Milestone 1 (see docs/adr/0007) - this needs the bypass before
        # the very first read, not after. Safe here for the same reason:
        # the lookup is keyed by a unique task_id, never a bulk scan.
        await set_platform_bypass(session)
        task = await jobs_repo.get_task(session, task_id)
        if task is None or task.status != "pending":
            return  # duplicate delivery or already handled by another worker
        tenant_id = task.tenant_id

    slot_index = await acquire_tenant_slot(str(tenant_id), task_id_str)
    if slot_index is None:
        raise _SlotUnavailable()

    try:
        async with AsyncSessionLocal() as session:
            await set_tenant_context(session, tenant_id)
            locked_task = await jobs_repo.lock_task_for_processing(
                session, task_id, locked_by=_WORKER_ID, now=_utcnow()
            )
            if locked_task is None:
                await session.commit()
                return

            campaign = await state_machine.get_campaign_or_raise(session, locked_task.campaign_id)
            job = await jobs_repo.get_job_or_raise(session, locked_task.job_id)

            if campaign.status == "queued":
                await state_machine.transition(
                    session, campaign, to_status="running", message="First page started"
                )
                job.status = "running"
                job.started_at = _utcnow()

            # Checked before doing any connector work, not just after -
            # this is what makes pause/cancel prompt instead of always
            # running at least one more page first.
            if campaign.status == "pausing":
                await _finalize_paused(session, campaign, job)
                locked_task.status = "cancelled"
                await session.commit()
                return
            if campaign.status == "cancelling":
                await _finalize_cancelled(session, campaign, job)
                locked_task.status = "cancelled"
                await session.commit()
                return

            campaign_filter = await campaigns_repo.get_filter_for_campaign_or_raise(
                session, campaign.id
            )
            query = build_search_query(campaign, campaign_filter, cursor=locked_task.cursor_in)
            source_key = campaign.source_key
            await session.commit()

        connector = get_connector(source_key)
        try:
            page = await connector.search(query)
        except (ConnectorAuthError, ConnectorPermanentError, ConnectorQuotaError) as exc:
            async with AsyncSessionLocal() as session:
                await set_tenant_context(session, tenant_id)
                task = await jobs_repo.get_task_or_raise(session, task_id)
                task.status = "failed"
                task.error_message = str(exc)
                campaign = await state_machine.get_campaign_or_raise(session, task.campaign_id)
                job = await jobs_repo.get_job_or_raise(session, task.job_id)
                await _finalize_failed(
                    session,
                    campaign,
                    job,
                    error_type=type(exc).__name__,
                    message=str(exc),
                    task_id=task_id,
                )
                await session.commit()
            return

        async with AsyncSessionLocal() as session:
            await set_tenant_context(session, tenant_id)
            task = await jobs_repo.get_task_or_raise(session, task_id)
            campaign = await state_machine.get_campaign_or_raise(session, task.campaign_id)
            job = await jobs_repo.get_job_or_raise(session, task.job_id)

            task.status = "succeeded"
            task.cursor_out = page.next_cursor
            task.businesses_found = len(page.businesses)
            task.result_snapshot = page.to_dict()
            job.current_cursor = page.next_cursor

            # AsyncSessionLocal is autoflush=False (see app.core.db), and the
            # finalize branches below read this task's own just-set status/
            # businesses_found back via a raw aggregate SELECT
            # (sum_succeeded_businesses_for_job), which does not trigger an
            # implicit flush. Without this explicit flush, the last page's
            # own count is silently dropped from the reservation commit.
            await session.flush()

            if campaign.status == "pausing":
                await _finalize_paused(session, campaign, job)
                await session.commit()
                return
            if campaign.status == "cancelling":
                await _finalize_cancelled(session, campaign, job)
                await session.commit()
                return

            if page.has_more:
                next_task = await jobs_repo.create_task(
                    session,
                    tenant_id=tenant_id,
                    campaign_id=campaign.id,
                    job_id=job.id,
                    page_number=task.page_number + 1,
                    cursor_in=page.next_cursor,
                )
                await session.commit()
                run_campaign_task.delay(str(next_task.id))
            else:
                await _finalize_completed(session, campaign, job)
                await session.commit()
    finally:
        await release_tenant_slot(str(tenant_id), slot_index, task_id_str)


@celery_app.task(bind=True, name="worker.campaign_tasks.run_campaign_task", max_retries=8)
def run_campaign_task(self, task_id: str) -> None:
    configure_logging()
    try:
        run_db_task(_run_campaign_task_async(task_id))
    except _SlotUnavailable:
        raise self.retry(countdown=15) from None
    except (ConnectorRateLimitError, ConnectorTransientError) as exc:
        backoff = min(60, 5 * (2**self.request.retries))
        try:
            raise self.retry(exc=exc, countdown=backoff) from exc
        except MaxRetriesExceededError:
            logger.warning("campaign_task_max_retries_exceeded", task_id=task_id, error=str(exc))
            run_db_task(
                _finalize_task_permanently_failed(
                    task_id, error_type=type(exc).__name__, message=str(exc)
                )
            )


async def _finalize_task_permanently_failed(
    task_id_str: str, *, error_type: str, message: str
) -> None:
    task_id = uuid.UUID(task_id_str)
    async with AsyncSessionLocal() as session:
        await set_platform_bypass(session)
        task = await jobs_repo.get_task(session, task_id)
        if task is None:
            return
        await set_tenant_context(session, task.tenant_id)
        task.status = "failed"
        task.error_message = message
        campaign = await state_machine.get_campaign_or_raise(session, task.campaign_id)
        job = await jobs_repo.get_job_or_raise(session, task.job_id)
        await _finalize_failed(
            session, campaign, job, error_type=error_type, message=message, task_id=task_id
        )
        await session.commit()
