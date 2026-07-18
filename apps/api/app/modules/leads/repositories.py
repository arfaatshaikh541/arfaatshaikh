import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.modules.businesses.models import Business
from app.modules.leads.models import (
    Lead,
    LeadAssignment,
    LeadNote,
    LeadOpportunity,
    LeadRecommendation,
    LeadScore,
    LeadStatusHistory,
    LeadTag,
    SavedLeadView,
)


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


# ---------------------------------------------------------------------------
# Lead list - server-side pagination/sorting/filtering (Milestone 6)
# ---------------------------------------------------------------------------

SORTABLE_COLUMNS = ("name", "score", "created_at", "status", "rating", "review_count")


@dataclass
class LeadListRow:
    lead: Lead
    business: Business
    latest_score: float | None


@dataclass
class LeadListFilters:
    statuses: list[str] | None = None
    assigned_to_user_id: uuid.UUID | None = None
    unassigned_only: bool = False
    tag: str | None = None
    opportunity_type: str | None = None
    category: str | None = None
    city: str | None = None
    country: str | None = None
    area: str | None = None
    min_score: float | None = None
    max_score: float | None = None
    search: str | None = None


def _latest_score_subquery():
    ranked = (
        select(
            LeadScore.lead_id,
            LeadScore.total_score,
            func.row_number()
            .over(partition_by=LeadScore.lead_id, order_by=LeadScore.calculated_at.desc())
            .label("rn"),
        )
    ).subquery()
    return select(ranked.c.lead_id, ranked.c.total_score).where(ranked.c.rn == 1).subquery()


async def list_leads(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    filters: LeadListFilters,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[LeadListRow], int]:
    """Only canonical businesses (see `businesses.repositories.
    list_businesses_for_campaign`'s same reasoning) - a Lead whose
    Business lost a Milestone 5 merge is excluded here, not deleted; see
    `businesses.dedup`'s module docstring for why."""
    latest_score = _latest_score_subquery()

    base = (
        select(Lead, Business, latest_score.c.total_score)
        .join(Business, Business.id == Lead.business_id)
        .outerjoin(latest_score, latest_score.c.lead_id == Lead.id)
        .where(Lead.tenant_id == tenant_id, Business.merged_into_id.is_(None))
    )

    if filters.statuses:
        base = base.where(Lead.status.in_(filters.statuses))
    if filters.unassigned_only:
        base = base.where(Lead.assigned_to_user_id.is_(None))
    elif filters.assigned_to_user_id is not None:
        base = base.where(Lead.assigned_to_user_id == filters.assigned_to_user_id)
    if filters.tag:
        base = base.where(
            Lead.id.in_(
                select(LeadTag.lead_id).where(
                    LeadTag.tenant_id == tenant_id, LeadTag.tag == filters.tag
                )
            )
        )
    if filters.opportunity_type:
        base = base.where(
            Lead.id.in_(
                select(LeadOpportunity.lead_id).where(
                    LeadOpportunity.tenant_id == tenant_id,
                    LeadOpportunity.opportunity_type == filters.opportunity_type,
                )
            )
        )
    if filters.category:
        base = base.where(Business.category == filters.category)
    if filters.city:
        base = base.where(Business.city == filters.city)
    if filters.country:
        base = base.where(Business.country == filters.country)
    if filters.area:
        base = base.where(Business.area == filters.area)
    if filters.min_score is not None:
        base = base.where(latest_score.c.total_score >= filters.min_score)
    if filters.max_score is not None:
        base = base.where(latest_score.c.total_score <= filters.max_score)
    if filters.search:
        base = base.where(Business.name.ilike(f"%{filters.search}%"))

    count_stmt = select(func.count()).select_from(base.with_only_columns(Lead.id).subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    sort_column = {
        "name": Business.name,
        "score": latest_score.c.total_score,
        "created_at": Lead.created_at,
        "status": Lead.status,
        "rating": Business.rating,
        "review_count": Business.review_count,
    }[sort_by if sort_by in SORTABLE_COLUMNS else "created_at"]
    ordered = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
    # NULLS LAST regardless of direction (unscored/unrated leads shouldn't
    # dominate the top of a descending sort just because NULL sorts first
    # by SQL default under some orderings).
    page_stmt = (
        base.order_by(ordered.nulls_last()).offset((max(page, 1) - 1) * page_size).limit(page_size)
    )
    rows = (await session.execute(page_stmt)).all()
    return [
        LeadListRow(lead=lead, business=business, latest_score=score)
        for lead, business, score in rows
    ], total


async def get_tags_for_leads(
    session: AsyncSession, lead_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[str]]:
    if not lead_ids:
        return {}
    stmt = select(LeadTag.lead_id, LeadTag.tag).where(LeadTag.lead_id.in_(lead_ids))
    result: dict[uuid.UUID, list[str]] = {}
    for lead_id, tag in (await session.execute(stmt)).all():
        result.setdefault(lead_id, []).append(tag)
    return result


# ---------------------------------------------------------------------------
# Status history
# ---------------------------------------------------------------------------


async def record_status_change(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    lead_id: uuid.UUID,
    from_status: str,
    to_status: str,
    changed_by_user_id: uuid.UUID | None,
    changed_at: datetime,
    note: str | None = None,
) -> LeadStatusHistory:
    entry = LeadStatusHistory(
        tenant_id=tenant_id,
        lead_id=lead_id,
        from_status=from_status,
        to_status=to_status,
        changed_by_user_id=changed_by_user_id,
        changed_at=changed_at,
        note=note,
    )
    session.add(entry)
    await session.flush()
    return entry


async def list_status_history(session: AsyncSession, lead_id: uuid.UUID) -> list[LeadStatusHistory]:
    stmt = (
        select(LeadStatusHistory)
        .where(LeadStatusHistory.lead_id == lead_id)
        .order_by(LeadStatusHistory.changed_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------


async def get_open_assignment(session: AsyncSession, lead_id: uuid.UUID) -> LeadAssignment | None:
    stmt = select(LeadAssignment).where(
        LeadAssignment.lead_id == lead_id, LeadAssignment.unassigned_at.is_(None)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_assignment(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    lead_id: uuid.UUID,
    assigned_to_user_id: uuid.UUID,
    assigned_by_user_id: uuid.UUID | None,
    assigned_at: datetime,
) -> LeadAssignment:
    entry = LeadAssignment(
        tenant_id=tenant_id,
        lead_id=lead_id,
        assigned_to_user_id=assigned_to_user_id,
        assigned_by_user_id=assigned_by_user_id,
        assigned_at=assigned_at,
    )
    session.add(entry)
    await session.flush()
    return entry


async def list_assignment_history(
    session: AsyncSession, lead_id: uuid.UUID
) -> list[LeadAssignment]:
    stmt = (
        select(LeadAssignment)
        .where(LeadAssignment.lead_id == lead_id)
        .order_by(LeadAssignment.assigned_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------


async def create_note(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    lead_id: uuid.UUID,
    author_user_id: uuid.UUID | None,
    body: str,
) -> LeadNote:
    note = LeadNote(tenant_id=tenant_id, lead_id=lead_id, author_user_id=author_user_id, body=body)
    session.add(note)
    await session.flush()
    return note


async def list_notes(session: AsyncSession, lead_id: uuid.UUID) -> list[LeadNote]:
    stmt = select(LeadNote).where(LeadNote.lead_id == lead_id).order_by(LeadNote.created_at.desc())
    return list((await session.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


async def get_tag(session: AsyncSession, *, lead_id: uuid.UUID, tag: str) -> LeadTag | None:
    stmt = select(LeadTag).where(LeadTag.lead_id == lead_id, LeadTag.tag == tag)
    return (await session.execute(stmt)).scalar_one_or_none()


async def add_tag(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    lead_id: uuid.UUID,
    tag: str,
    created_by_user_id: uuid.UUID | None,
) -> LeadTag:
    existing = await get_tag(session, lead_id=lead_id, tag=tag)
    if existing is not None:
        return existing
    entry = LeadTag(
        tenant_id=tenant_id, lead_id=lead_id, tag=tag, created_by_user_id=created_by_user_id
    )
    session.add(entry)
    await session.flush()
    return entry


async def remove_tag(session: AsyncSession, *, lead_id: uuid.UUID, tag: str) -> bool:
    existing = await get_tag(session, lead_id=lead_id, tag=tag)
    if existing is None:
        return False
    await session.delete(existing)
    await session.flush()
    return True


async def list_tags(session: AsyncSession, lead_id: uuid.UUID) -> list[str]:
    stmt = select(LeadTag.tag).where(LeadTag.lead_id == lead_id).order_by(LeadTag.tag)
    return list((await session.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# Saved views
# ---------------------------------------------------------------------------


async def create_saved_view(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    name: str,
    created_by_user_id: uuid.UUID | None,
    filters: dict,
) -> SavedLeadView:
    view = SavedLeadView(
        tenant_id=tenant_id, name=name, created_by_user_id=created_by_user_id, filters=filters
    )
    session.add(view)
    await session.flush()
    return view


async def list_saved_views(session: AsyncSession, tenant_id: uuid.UUID) -> list[SavedLeadView]:
    stmt = (
        select(SavedLeadView)
        .where(SavedLeadView.tenant_id == tenant_id)
        .order_by(SavedLeadView.name)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_saved_view(session: AsyncSession, view_id: uuid.UUID) -> SavedLeadView | None:
    stmt = select(SavedLeadView).where(SavedLeadView.id == view_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_saved_view_or_raise(session: AsyncSession, view_id: uuid.UUID) -> SavedLeadView:
    view = await get_saved_view(session, view_id)
    if view is None:
        raise ResourceNotFoundError("Saved view not found.")
    return view
