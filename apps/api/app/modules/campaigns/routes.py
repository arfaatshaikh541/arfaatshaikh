import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_client import enqueue_campaign_task
from app.core.db import get_db
from app.dependencies import TenantContext, require_permission
from app.modules.businesses import repositories as businesses_repo
from app.modules.businesses.schemas import BusinessResponse
from app.modules.campaigns import repositories as repo
from app.modules.campaigns import services, state_machine
from app.modules.campaigns.schemas import (
    CampaignDetailResponse,
    CampaignErrorResponse,
    CampaignEventResponse,
    CampaignFilterResponse,
    CampaignResponse,
    CreateCampaignRequest,
    EstimateResponse,
    ProgressResponse,
)
from app.modules.usage.services import get_available_balance

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _to_campaign_response(campaign) -> CampaignResponse:
    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        source_key=campaign.source_key,
        status=campaign.status,
        result_limit=campaign.result_limit,
        created_at=campaign.created_at,
    )


@router.post("", response_model=CampaignResponse)
async def create_campaign(
    payload: CreateCampaignRequest,
    ctx: TenantContext = Depends(require_permission("campaigns.create")),
    db: AsyncSession = Depends(get_db),
):
    campaign = await services.create_campaign(
        db, tenant_id=ctx.tenant_id, user_id=ctx.user_id, payload=payload
    )
    return _to_campaign_response(campaign)


@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(
    ctx: TenantContext = Depends(require_permission("campaigns.view")),
    db: AsyncSession = Depends(get_db),
):
    campaigns = await repo.list_campaigns_for_tenant(db, ctx.tenant_id)
    return [_to_campaign_response(c) for c in campaigns]


@router.get("/{campaign_id}", response_model=CampaignDetailResponse)
async def get_campaign(
    campaign_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("campaigns.view")),
    db: AsyncSession = Depends(get_db),
):
    campaign = await state_machine.get_campaign_or_raise(db, campaign_id)
    campaign_filter = await repo.get_filter_for_campaign(db, campaign_id)
    estimate = await repo.get_usage_estimate(db, campaign_id)
    return CampaignDetailResponse(
        **_to_campaign_response(campaign).model_dump(),
        filter=CampaignFilterResponse.model_validate(campaign_filter, from_attributes=True),
        estimated_credits=float(estimate.estimated_credits) if estimate else None,
        estimated_results=estimate.estimated_results if estimate else None,
    )


@router.post("/{campaign_id}/estimate", response_model=EstimateResponse)
async def estimate_campaign(
    campaign_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("campaigns.create")),
    db: AsyncSession = Depends(get_db),
):
    campaign, estimate = await services.compute_estimate(db, campaign_id=campaign_id)
    available = await get_available_balance(db, ctx.tenant_id)
    return EstimateResponse(
        campaign_id=campaign.id,
        estimated_credits=float(estimate.estimated_credits),
        estimated_results=estimate.estimated_results,
        calculated_at=estimate.calculated_at,
        available_balance=available,
    )


@router.post("/{campaign_id}/launch", response_model=CampaignResponse)
async def launch_campaign(
    campaign_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("campaigns.start")),
    db: AsyncSession = Depends(get_db),
):
    campaign, job, task = await services.launch_campaign(db, campaign_id=campaign_id)
    # Commit before enqueueing: the worker must never be able to consume
    # the Celery message before the job/task rows it needs are visible.
    await db.commit()
    enqueue_campaign_task(str(task.id))
    return _to_campaign_response(campaign)


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("campaigns.pause")),
    db: AsyncSession = Depends(get_db),
):
    campaign = await services.pause_campaign(db, campaign_id=campaign_id)
    return _to_campaign_response(campaign)


@router.post("/{campaign_id}/resume", response_model=CampaignResponse)
async def resume_campaign(
    campaign_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("campaigns.start")),
    db: AsyncSession = Depends(get_db),
):
    campaign, job, task = await services.resume_campaign(db, campaign_id=campaign_id)
    await db.commit()
    enqueue_campaign_task(str(task.id))
    return _to_campaign_response(campaign)


@router.post("/{campaign_id}/cancel", response_model=CampaignResponse)
async def cancel_campaign(
    campaign_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("campaigns.cancel")),
    db: AsyncSession = Depends(get_db),
):
    campaign = await services.cancel_campaign(db, campaign_id=campaign_id)
    return _to_campaign_response(campaign)


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("campaigns.delete")),
    db: AsyncSession = Depends(get_db),
):
    await services.delete_campaign(db, campaign_id=campaign_id)


@router.get("/{campaign_id}/progress", response_model=ProgressResponse)
async def get_progress(
    campaign_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("campaigns.view")),
    db: AsyncSession = Depends(get_db),
):
    progress = await services.get_progress(db, campaign_id=campaign_id)
    return ProgressResponse(**progress)


@router.get("/{campaign_id}/events", response_model=list[CampaignEventResponse])
async def list_events(
    campaign_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("campaigns.view")),
    db: AsyncSession = Depends(get_db),
):
    events = await repo.list_events_for_campaign(db, campaign_id)
    return [
        CampaignEventResponse(
            id=e.id,
            event_type=e.event_type,
            from_status=e.from_status,
            to_status=e.to_status,
            message=e.message,
            created_at=e.created_at,
        )
        for e in events
    ]


@router.get("/{campaign_id}/errors", response_model=list[CampaignErrorResponse])
async def list_errors(
    campaign_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("campaigns.view")),
    db: AsyncSession = Depends(get_db),
):
    errors = await repo.list_errors_for_campaign(db, campaign_id)
    return [
        CampaignErrorResponse(
            id=e.id, error_type=e.error_type, message=e.message, created_at=e.created_at
        )
        for e in errors
    ]


@router.get("/{campaign_id}/businesses", response_model=list[BusinessResponse])
async def list_businesses(
    campaign_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    businesses = await businesses_repo.list_businesses_for_campaign(db, campaign_id)
    return [BusinessResponse.from_model(b) for b in businesses]
