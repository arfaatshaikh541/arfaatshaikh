"""Campaign lifecycle services: create, estimate, launch, pause, resume,
cancel, delete.

Credit flow: `compute_estimate` never reserves anything - it only
computes and stores a `CampaignUsageEstimate`. `launch_campaign` is the
only place that calls `usage.services.reserve_credits`, and the worker's
task-completion/cancellation/failure paths are the only places that call
`commit_reservation` (see `worker.campaign_tasks`) - this file never
commits or releases a reservation itself, since only the worker knows the
actual amount consumed.
"""

import uuid
from datetime import UTC, datetime

from connector_sdk import SearchQuery
from connector_sdk.registry import get_connector
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ResourceNotFoundError, ValidationAppError
from app.modules.campaign_jobs import repositories as jobs_repo
from app.modules.campaigns import repositories as repo
from app.modules.campaigns import state_machine
from app.modules.campaigns.models import Campaign, CampaignFilter
from app.modules.campaigns.schemas import WEBSITE_REQUIREMENTS, CreateCampaignRequest
from app.modules.entitlements.service import check_limit
from app.modules.usage.services import commit_reservation, release_reservation, reserve_credits


def build_search_query(
    campaign: Campaign, campaign_filter: CampaignFilter, *, cursor: str | None
) -> SearchQuery:
    return SearchQuery(
        industry=campaign_filter.industry,
        category=campaign_filter.category,
        subcategory=campaign_filter.subcategory,
        country=campaign_filter.country,
        region=campaign_filter.region,
        city=campaign_filter.city,
        area=campaign_filter.area,
        radius_km=float(campaign_filter.radius_km)
        if campaign_filter.radius_km is not None
        else None,
        min_rating=float(campaign_filter.min_rating)
        if campaign_filter.min_rating is not None
        else None,
        min_reviews=campaign_filter.min_reviews,
        must_have_phone=campaign_filter.must_have_phone,
        website_requirement=campaign_filter.website_requirement,
        business_status=campaign_filter.business_status,
        result_limit=campaign.result_limit,
        cursor=cursor,
    )


async def create_campaign(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    payload: CreateCampaignRequest,
) -> Campaign:
    if payload.website_requirement not in WEBSITE_REQUIREMENTS:
        raise ValidationAppError(f"website_requirement must be one of {WEBSITE_REQUIREMENTS}")
    try:
        connector = get_connector(payload.source_key)
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc

    if not connector.supports_rating_filter and (
        payload.min_rating is not None or payload.min_reviews is not None
    ):
        raise ValidationAppError(
            f"The {payload.source_key!r} connector has no rating/review data - "
            "remove min_rating/min_reviews to use this source."
        )

    campaign = await repo.create_campaign(
        session,
        tenant_id=tenant_id,
        name=payload.name,
        source_key=payload.source_key,
        result_limit=payload.result_limit,
        created_by_user_id=user_id,
    )
    await repo.create_filter(
        session,
        tenant_id=tenant_id,
        campaign_id=campaign.id,
        industry=payload.industry,
        category=payload.category,
        subcategory=payload.subcategory,
        country=payload.country,
        region=payload.region,
        city=payload.city,
        area=payload.area,
        radius_km=payload.radius_km,
        min_rating=payload.min_rating,
        min_reviews=payload.min_reviews,
        must_have_phone=payload.must_have_phone,
        website_requirement=payload.website_requirement,
        business_status=payload.business_status,
    )
    await repo.record_event(
        session,
        tenant_id=tenant_id,
        campaign_id=campaign.id,
        event_type="created",
        to_status="draft",
    )
    return campaign


async def compute_estimate(session: AsyncSession, *, campaign_id: uuid.UUID):
    campaign = await state_machine.get_campaign_or_raise(session, campaign_id)
    if campaign.status not in ("draft", "ready"):
        raise ConflictError(f"Cannot estimate a campaign in status '{campaign.status}'.")

    campaign_filter = await repo.get_filter_for_campaign(session, campaign_id)
    if campaign_filter is None:
        raise ResourceNotFoundError("Campaign filter not found.")

    if campaign.status == "draft":
        await state_machine.transition(
            session, campaign, to_status="estimating", message="Estimate requested"
        )

    connector = get_connector(campaign.source_key)
    query = build_search_query(campaign, campaign_filter, cursor=None)
    estimated_credits = await connector.estimate_cost(query)

    now = datetime.now(UTC)
    estimate = await repo.upsert_usage_estimate(
        session,
        tenant_id=campaign.tenant_id,
        campaign_id=campaign.id,
        estimated_credits=estimated_credits,
        estimated_results=campaign.result_limit,
        calculated_at=now,
    )
    await state_machine.transition(session, campaign, to_status="ready", message="Estimate ready")
    return campaign, estimate


async def launch_campaign(session: AsyncSession, *, campaign_id: uuid.UUID):
    campaign = await state_machine.get_campaign_or_raise(session, campaign_id)
    if campaign.status != "ready":
        raise ConflictError("Campaign must be in 'ready' status to launch.")

    active_count = await repo.count_active_campaigns_for_tenant(session, campaign.tenant_id)
    await check_limit(session, campaign.tenant_id, "max_concurrent_campaigns", active_count)

    estimate = await repo.get_usage_estimate(session, campaign.id)
    if estimate is None:
        raise ConflictError("Campaign has no usage estimate. Estimate it before launching.")

    reservation = await reserve_credits(
        session,
        tenant_id=campaign.tenant_id,
        amount=float(estimate.estimated_credits),
        reference=f"campaign:{campaign.id}",
    )
    campaign.reservation_id = reservation.id

    await state_machine.transition(
        session, campaign, to_status="queued", message="Campaign launched"
    )

    job = await jobs_repo.create_job(session, tenant_id=campaign.tenant_id, campaign_id=campaign.id)
    task = await jobs_repo.create_task(
        session,
        tenant_id=campaign.tenant_id,
        campaign_id=campaign.id,
        job_id=job.id,
        page_number=0,
        cursor_in=None,
    )
    return campaign, job, task


async def pause_campaign(session: AsyncSession, *, campaign_id: uuid.UUID) -> Campaign:
    campaign = await state_machine.get_campaign_or_raise(session, campaign_id)
    if campaign.status != "running":
        raise ConflictError("Only a running campaign can be paused.")
    await state_machine.transition(
        session, campaign, to_status="pausing", message="Pause requested"
    )
    return campaign


async def resume_campaign(session: AsyncSession, *, campaign_id: uuid.UUID):
    campaign = await state_machine.get_campaign_or_raise(session, campaign_id)
    if campaign.status != "paused":
        raise ConflictError("Only a paused campaign can be resumed.")

    job = await jobs_repo.get_latest_job_for_campaign(session, campaign_id)
    if job is None:
        raise ConflictError("Campaign has no job to resume.")

    await state_machine.transition(
        session, campaign, to_status="queued", message="Resume requested"
    )
    job.status = "queued"

    existing_tasks = await jobs_repo.list_tasks_for_job(session, job.id)
    next_page = max((t.page_number for t in existing_tasks), default=-1) + 1
    task = await jobs_repo.create_task(
        session,
        tenant_id=campaign.tenant_id,
        campaign_id=campaign.id,
        job_id=job.id,
        page_number=next_page,
        cursor_in=job.current_cursor,
    )
    return campaign, job, task


async def cancel_campaign(session: AsyncSession, *, campaign_id: uuid.UUID) -> Campaign:
    campaign = await state_machine.get_campaign_or_raise(session, campaign_id)
    if campaign.status not in ("queued", "running", "paused"):
        raise ConflictError(f"Cannot cancel a campaign in status '{campaign.status}'.")

    # A campaign always has a job+first task by the time it reaches
    # "queued" (launch_campaign creates both eagerly), so "queued" and
    # "running" always have a pending-or-in-flight task that the worker
    # will pick up and finalize once it observes "cancelling" (see
    # worker.campaign_tasks). Only "paused" has no such task waiting - the
    # previous task already finished and no follow-up was ever created -
    # so that case must be finalized synchronously, right here.
    was_paused = campaign.status == "paused"
    await state_machine.transition(
        session, campaign, to_status="cancelling", message="Cancel requested"
    )

    if was_paused:
        await _finalize_cancelled_synchronously(session, campaign)
    return campaign


async def _finalize_cancelled_synchronously(session: AsyncSession, campaign: Campaign) -> None:
    job = await jobs_repo.get_latest_job_for_campaign(session, campaign.id)
    if job is not None:
        job.status = "cancelled"
        total_found = await jobs_repo.sum_succeeded_businesses_for_job(session, job.id)
    else:
        total_found = 0

    if campaign.reservation_id:
        if total_found > 0:
            await commit_reservation(
                session, reservation_id=campaign.reservation_id, actual_amount=float(total_found)
            )
        else:
            await release_reservation(session, reservation_id=campaign.reservation_id)

    await state_machine.transition(
        session, campaign, to_status="cancelled", message="Cancelled while paused"
    )


async def delete_campaign(session: AsyncSession, *, campaign_id: uuid.UUID) -> None:
    campaign = await state_machine.get_campaign_or_raise(session, campaign_id)
    if not state_machine.is_terminal(campaign.status) and campaign.status not in (
        "draft",
        "estimating",
        "ready",
    ):
        raise ConflictError(
            f"Cannot delete an active campaign (status='{campaign.status}'). Cancel it first."
        )
    await session.delete(campaign)


async def get_progress(session: AsyncSession, *, campaign_id: uuid.UUID) -> dict:
    campaign = await state_machine.get_campaign_or_raise(session, campaign_id)
    job = await jobs_repo.get_latest_job_for_campaign(session, campaign_id)

    if job is None:
        return {
            "campaign_id": campaign.id,
            "status": campaign.status,
            "job_status": None,
            "total_tasks": 0,
            "succeeded_tasks": 0,
            "failed_tasks": 0,
            "pending_tasks": 0,
            "businesses_found": 0,
        }

    counts = await jobs_repo.task_status_counts_for_job(session, job.id)
    businesses_found = await jobs_repo.sum_succeeded_businesses_for_job(session, job.id)
    return {
        "campaign_id": campaign.id,
        "status": campaign.status,
        "job_status": job.status,
        "total_tasks": sum(counts.values()),
        "succeeded_tasks": counts.get("succeeded", 0),
        "failed_tasks": counts.get("failed", 0),
        "pending_tasks": counts.get("pending", 0) + counts.get("running", 0),
        "businesses_found": businesses_found,
    }
