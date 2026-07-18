import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.modules.campaigns.models import (
    Campaign,
    CampaignError,
    CampaignEvent,
    CampaignFilter,
    CampaignUsageEstimate,
)


async def create_campaign(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    name: str,
    source_key: str,
    result_limit: int,
    created_by_user_id: uuid.UUID | None,
) -> Campaign:
    campaign = Campaign(
        tenant_id=tenant_id,
        name=name,
        source_key=source_key,
        result_limit=result_limit,
        created_by_user_id=created_by_user_id,
        status="draft",
    )
    session.add(campaign)
    await session.flush()
    return campaign


async def get_campaign(session: AsyncSession, campaign_id: uuid.UUID) -> Campaign | None:
    stmt = select(Campaign).where(Campaign.id == campaign_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_campaigns_for_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> list[Campaign]:
    stmt = (
        select(Campaign).where(Campaign.tenant_id == tenant_id).order_by(Campaign.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_campaigns_by_ids(
    session: AsyncSession, campaign_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Campaign]:
    if not campaign_ids:
        return {}
    stmt = select(Campaign).where(Campaign.id.in_(campaign_ids))
    return {c.id: c for c in (await session.execute(stmt)).scalars().all()}


async def count_active_campaigns_for_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    stmt = select(Campaign).where(
        Campaign.tenant_id == tenant_id,
        Campaign.status.in_(["queued", "running", "pausing", "paused", "cancelling"]),
    )
    return len((await session.execute(stmt)).scalars().all())


async def create_filter(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    campaign_id: uuid.UUID,
    industry: str,
    category: str | None,
    subcategory: str | None,
    country: str,
    region: str | None,
    city: str,
    area: str | None,
    radius_km: float | None,
    min_rating: float | None,
    min_reviews: int | None,
    must_have_phone: bool,
    website_requirement: str,
    business_status: str | None,
) -> CampaignFilter:
    campaign_filter = CampaignFilter(
        tenant_id=tenant_id,
        campaign_id=campaign_id,
        industry=industry,
        category=category,
        subcategory=subcategory,
        country=country,
        region=region,
        city=city,
        area=area,
        radius_km=radius_km,
        min_rating=min_rating,
        min_reviews=min_reviews,
        must_have_phone=must_have_phone,
        website_requirement=website_requirement,
        business_status=business_status,
    )
    session.add(campaign_filter)
    await session.flush()
    return campaign_filter


async def get_filter_for_campaign(
    session: AsyncSession, campaign_id: uuid.UUID
) -> CampaignFilter | None:
    stmt = select(CampaignFilter).where(CampaignFilter.campaign_id == campaign_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_filter_for_campaign_or_raise(
    session: AsyncSession, campaign_id: uuid.UUID
) -> CampaignFilter:
    campaign_filter = await get_filter_for_campaign(session, campaign_id)
    if campaign_filter is None:
        raise ResourceNotFoundError("Campaign filter not found.")
    return campaign_filter


async def upsert_usage_estimate(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    campaign_id: uuid.UUID,
    estimated_credits: float,
    estimated_results: int,
    calculated_at: datetime,
) -> CampaignUsageEstimate:
    existing = await get_usage_estimate(session, campaign_id)
    if existing is not None:
        existing.estimated_credits = estimated_credits
        existing.estimated_results = estimated_results
        existing.calculated_at = calculated_at
        return existing
    estimate = CampaignUsageEstimate(
        tenant_id=tenant_id,
        campaign_id=campaign_id,
        estimated_credits=estimated_credits,
        estimated_results=estimated_results,
        calculated_at=calculated_at,
    )
    session.add(estimate)
    await session.flush()
    return estimate


async def get_usage_estimate(
    session: AsyncSession, campaign_id: uuid.UUID
) -> CampaignUsageEstimate | None:
    stmt = select(CampaignUsageEstimate).where(CampaignUsageEstimate.campaign_id == campaign_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def record_event(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    campaign_id: uuid.UUID,
    event_type: str,
    from_status: str | None = None,
    to_status: str | None = None,
    message: str | None = None,
    metadata: dict | None = None,
) -> CampaignEvent:
    event = CampaignEvent(
        tenant_id=tenant_id,
        campaign_id=campaign_id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        message=message,
        metadata_json=metadata or {},
    )
    session.add(event)
    await session.flush()
    return event


async def list_events_for_campaign(
    session: AsyncSession, campaign_id: uuid.UUID
) -> list[CampaignEvent]:
    stmt = (
        select(CampaignEvent)
        .where(CampaignEvent.campaign_id == campaign_id)
        .order_by(CampaignEvent.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def record_error(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    campaign_id: uuid.UUID,
    task_id: uuid.UUID | None,
    error_type: str,
    message: str,
) -> CampaignError:
    error = CampaignError(
        tenant_id=tenant_id,
        campaign_id=campaign_id,
        task_id=task_id,
        error_type=error_type,
        message=message,
    )
    session.add(error)
    await session.flush()
    return error


async def list_errors_for_campaign(
    session: AsyncSession, campaign_id: uuid.UUID
) -> list[CampaignError]:
    stmt = (
        select(CampaignError)
        .where(CampaignError.campaign_id == campaign_id)
        .order_by(CampaignError.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())
