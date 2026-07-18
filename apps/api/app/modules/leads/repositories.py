import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.modules.leads.models import Lead, LeadOpportunity, LeadRecommendation, LeadScore


async def get_lead(session: AsyncSession, lead_id: uuid.UUID) -> Lead | None:
    stmt = select(Lead).where(Lead.id == lead_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_lead_or_raise(session: AsyncSession, lead_id: uuid.UUID) -> Lead:
    lead = await get_lead(session, lead_id)
    if lead is None:
        raise ResourceNotFoundError("Lead not found.")
    return lead


async def get_lead_for_business(session: AsyncSession, business_id: uuid.UUID) -> Lead | None:
    stmt = select(Lead).where(Lead.business_id == business_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_or_create_lead(
    session: AsyncSession, *, tenant_id: uuid.UUID, business_id: uuid.UUID
) -> Lead:
    lead = await get_lead_for_business(session, business_id)
    if lead is not None:
        return lead
    lead = Lead(tenant_id=tenant_id, business_id=business_id, status="new")
    session.add(lead)
    await session.flush()
    return lead


async def create_score(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    lead_id: uuid.UUID,
    algorithm_version: str,
    total_score: float,
    max_score: float,
    factors: list[dict],
    calculated_at: datetime,
) -> LeadScore:
    score = LeadScore(
        tenant_id=tenant_id,
        lead_id=lead_id,
        algorithm_version=algorithm_version,
        total_score=total_score,
        max_score=max_score,
        factors=factors,
        calculated_at=calculated_at,
    )
    session.add(score)
    await session.flush()
    return score


async def get_latest_score_for_lead(session: AsyncSession, lead_id: uuid.UUID) -> LeadScore | None:
    stmt = (
        select(LeadScore)
        .where(LeadScore.lead_id == lead_id)
        .order_by(LeadScore.calculated_at.desc())
    )
    return (await session.execute(stmt)).scalars().first()


async def list_scores_for_lead(session: AsyncSession, lead_id: uuid.UUID) -> list[LeadScore]:
    stmt = (
        select(LeadScore)
        .where(LeadScore.lead_id == lead_id)
        .order_by(LeadScore.calculated_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def replace_opportunities(
    session: AsyncSession, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, opportunities: list[dict]
) -> list[LeadOpportunity]:
    """Upserts by (lead_id, opportunity_type) - a re-score reflects the
    business's *current* state, so an opportunity no longer detected
    (e.g. the business added online booking since the last crawl) should
    stop being listed, and one still present should keep its original
    `detected_at` rather than appearing freshly "discovered" every time."""
    existing_stmt = select(LeadOpportunity).where(LeadOpportunity.lead_id == lead_id)
    existing_by_type = {
        o.opportunity_type: o for o in (await session.execute(existing_stmt)).scalars().all()
    }

    current_types = {o["opportunity_type"] for o in opportunities}
    for opportunity_type, existing in existing_by_type.items():
        if opportunity_type not in current_types:
            await session.delete(existing)

    results: list[LeadOpportunity] = []
    for data in opportunities:
        existing_opportunity = existing_by_type.get(data["opportunity_type"])
        if existing_opportunity is not None:
            existing_opportunity.confidence = data["confidence"]
            existing_opportunity.evidence_reference = data["evidence_reference"]
            results.append(existing_opportunity)
        else:
            new_opportunity = LeadOpportunity(
                tenant_id=tenant_id,
                lead_id=lead_id,
                opportunity_type=data["opportunity_type"],
                confidence=data["confidence"],
                evidence_reference=data["evidence_reference"],
                detected_at=data["detected_at"],
            )
            session.add(new_opportunity)
            results.append(new_opportunity)
    await session.flush()
    return results


async def list_opportunities_for_lead(
    session: AsyncSession, lead_id: uuid.UUID
) -> list[LeadOpportunity]:
    stmt = (
        select(LeadOpportunity)
        .where(LeadOpportunity.lead_id == lead_id)
        .order_by(LeadOpportunity.confidence.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def replace_recommendations(
    session: AsyncSession, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, recommendations: list[dict]
) -> list[LeadRecommendation]:
    existing_stmt = select(LeadRecommendation).where(LeadRecommendation.lead_id == lead_id)
    existing_by_type = {
        r.recommendation_type: r for r in (await session.execute(existing_stmt)).scalars().all()
    }

    current_types = {r["recommendation_type"] for r in recommendations}
    for recommendation_type, existing in existing_by_type.items():
        if recommendation_type not in current_types:
            await session.delete(existing)

    results: list[LeadRecommendation] = []
    for data in recommendations:
        existing_recommendation = existing_by_type.get(data["recommendation_type"])
        if existing_recommendation is not None:
            existing_recommendation.confidence = data["confidence"]
            existing_recommendation.supporting_opportunity_ids = data["supporting_opportunity_ids"]
            results.append(existing_recommendation)
        else:
            new_recommendation = LeadRecommendation(
                tenant_id=tenant_id,
                lead_id=lead_id,
                recommendation_type=data["recommendation_type"],
                confidence=data["confidence"],
                supporting_opportunity_ids=data["supporting_opportunity_ids"],
                recommended_at=data["recommended_at"],
            )
            session.add(new_recommendation)
            results.append(new_recommendation)
    await session.flush()
    return results


async def list_recommendations_for_lead(
    session: AsyncSession, lead_id: uuid.UUID
) -> list[LeadRecommendation]:
    stmt = (
        select(LeadRecommendation)
        .where(LeadRecommendation.lead_id == lead_id)
        .order_by(LeadRecommendation.confidence.desc())
    )
    return list((await session.execute(stmt)).scalars().all())
