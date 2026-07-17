import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.modules.campaign_jobs.models import CampaignJob, CampaignTask


async def create_job(
    session: AsyncSession, *, tenant_id: uuid.UUID, campaign_id: uuid.UUID
) -> CampaignJob:
    job = CampaignJob(tenant_id=tenant_id, campaign_id=campaign_id, status="queued")
    session.add(job)
    await session.flush()
    return job


async def get_job(session: AsyncSession, job_id: uuid.UUID) -> CampaignJob | None:
    stmt = select(CampaignJob).where(CampaignJob.id == job_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_job_or_raise(session: AsyncSession, job_id: uuid.UUID) -> CampaignJob:
    job = await get_job(session, job_id)
    if job is None:
        raise ResourceNotFoundError("Campaign job not found.")
    return job


async def get_latest_job_for_campaign(
    session: AsyncSession, campaign_id: uuid.UUID
) -> CampaignJob | None:
    stmt = (
        select(CampaignJob)
        .where(CampaignJob.campaign_id == campaign_id)
        .order_by(CampaignJob.created_at.desc())
    )
    return (await session.execute(stmt)).scalars().first()


async def count_active_jobs_for_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    stmt = select(CampaignJob).where(
        CampaignJob.tenant_id == tenant_id, CampaignJob.status.in_(["queued", "running"])
    )
    return len((await session.execute(stmt)).scalars().all())


async def create_task(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    campaign_id: uuid.UUID,
    job_id: uuid.UUID,
    page_number: int,
    cursor_in: str | None,
) -> CampaignTask:
    task = CampaignTask(
        tenant_id=tenant_id,
        campaign_id=campaign_id,
        job_id=job_id,
        idempotency_key=f"{job_id}:{page_number}",
        page_number=page_number,
        cursor_in=cursor_in,
        status="pending",
    )
    session.add(task)
    await session.flush()
    return task


async def get_task(session: AsyncSession, task_id: uuid.UUID) -> CampaignTask | None:
    stmt = select(CampaignTask).where(CampaignTask.id == task_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_task_or_raise(session: AsyncSession, task_id: uuid.UUID) -> CampaignTask:
    task = await get_task(session, task_id)
    if task is None:
        raise ResourceNotFoundError("Campaign task not found.")
    return task


async def list_tasks_for_job(session: AsyncSession, job_id: uuid.UUID) -> list[CampaignTask]:
    stmt = (
        select(CampaignTask).where(CampaignTask.job_id == job_id).order_by(CampaignTask.page_number)
    )
    return list((await session.execute(stmt)).scalars().all())


async def sum_succeeded_businesses_for_job(session: AsyncSession, job_id: uuid.UUID) -> int:
    stmt = select(func.coalesce(func.sum(CampaignTask.businesses_found), 0)).where(
        CampaignTask.job_id == job_id, CampaignTask.status == "succeeded"
    )
    return int((await session.execute(stmt)).scalar_one())


async def task_status_counts_for_job(session: AsyncSession, job_id: uuid.UUID) -> dict[str, int]:
    tasks = await list_tasks_for_job(session, job_id)
    counts: dict[str, int] = {}
    for task in tasks:
        counts[task.status] = counts.get(task.status, 0) + 1
    return counts


async def lock_task_for_processing(
    session: AsyncSession, task_id: uuid.UUID, *, locked_by: str, now: datetime
) -> CampaignTask | None:
    """Idempotency guard: only transitions a task pending -> running and
    claims it for `locked_by`. Returns None (no-op) if the task is not in
    a claimable state - e.g. a retried/duplicated Celery delivery for a
    task another worker already completed or is already processing."""
    task = await get_task(session, task_id)
    if task is None or task.status != "pending":
        return None
    task.status = "running"
    task.locked_by = locked_by
    task.locked_at = now
    task.attempt_count += 1
    return task
