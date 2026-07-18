import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.dependencies import TenantContext, require_permission
from app.modules.businesses import repositories as businesses_repo
from app.modules.leads import repositories as leads_repo
from app.modules.leads import services
from app.modules.leads.models import LEAD_STATUSES
from app.modules.leads.repositories import LeadListFilters
from app.modules.leads.schemas import (
    AddNoteRequest,
    AddTagRequest,
    AssignmentResponse,
    AssignRequest,
    BulkAssignRequest,
    BulkStatusRequest,
    BulkTagRequest,
    ChangeStatusRequest,
    DuplicateCandidateResponse,
    LeadDetailResponse,
    LeadListItemResponse,
    LeadListResponse,
    LeadOpportunityResponse,
    LeadRecommendationResponse,
    LeadResponse,
    LeadScoreResponse,
    NoteResponse,
    SavedViewCreateRequest,
    SavedViewResponse,
    StatusHistoryResponse,
    TagResponse,
)

router = APIRouter(prefix="/leads", tags=["leads"])
saved_views_router = APIRouter(prefix="/saved-views", tags=["leads"])


def _to_score_response(score) -> LeadScoreResponse:
    return LeadScoreResponse(
        id=score.id,
        algorithm_version=score.algorithm_version,
        total_score=float(score.total_score),
        max_score=float(score.max_score),
        factors=score.factors,
        calculated_at=score.calculated_at,
    )


@router.get("", response_model=LeadListResponse)
async def list_leads(
    status_filter: list[str] | None = Query(default=None, alias="status"),
    assigned_to_user_id: uuid.UUID | None = Query(default=None),
    unassigned_only: bool = Query(default=False),
    tag: str | None = Query(default=None),
    opportunity_type: str | None = Query(default=None),
    category: str | None = Query(default=None),
    city: str | None = Query(default=None),
    country: str | None = Query(default=None),
    area: str | None = Query(default=None),
    min_score: float | None = Query(default=None),
    max_score: float | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    filters = LeadListFilters(
        statuses=status_filter,
        assigned_to_user_id=assigned_to_user_id,
        unassigned_only=unassigned_only,
        tag=tag,
        opportunity_type=opportunity_type,
        category=category,
        city=city,
        country=country,
        area=area,
        min_score=min_score,
        max_score=max_score,
        search=search,
    )
    rows, total = await leads_repo.list_leads(
        db,
        tenant_id=ctx.tenant_id,
        filters=filters,
        sort_by=sort_by,
        sort_dir="asc" if sort_dir == "asc" else "desc",
        page=page,
        page_size=page_size,
    )
    tags_by_lead = await leads_repo.get_tags_for_leads(db, [row.lead.id for row in rows])
    items = [
        LeadListItemResponse(
            lead_id=row.lead.id,
            business_id=row.business.id,
            business_name=row.business.name,
            category=row.business.category,
            city=row.business.city,
            country=row.business.country,
            area=row.business.area,
            phone=row.business.phone,
            email=row.business.email,
            website=row.business.website,
            rating=float(row.business.rating) if row.business.rating is not None else None,
            review_count=row.business.review_count,
            business_status=row.business.business_status,
            status=row.lead.status,
            assigned_to_user_id=row.lead.assigned_to_user_id,
            score=float(row.latest_score) if row.latest_score is not None else None,
            tags=tags_by_lead.get(row.lead.id, []),
            created_at=row.lead.created_at,
        )
        for row in rows
    ]
    return LeadListResponse(items=items, total=total, page=page, page_size=page_size)


# NOTE: every route below with a literal path segment at the same
# position a `/{lead_id}/...` route would occupy (`/bulk/status` vs
# `/{lead_id}/status`, etc.) MUST be registered before that `/{lead_id}`
# route - Starlette matches routes in registration order, and a
# parameterized segment matches any string, including "bulk" or "meta".
# Registering these first (right after the collection-level `list_leads`
# route above) keeps every such collision resolved by construction rather
# than by hoping nobody reorders things later.


@router.get("/meta/statuses", response_model=list[str])
async def list_lead_statuses(
    ctx: TenantContext = Depends(require_permission("leads.view")),
):
    return list(LEAD_STATUSES)


@router.post("/bulk/status", response_model=list[LeadResponse])
async def bulk_change_status(
    payload: BulkStatusRequest,
    ctx: TenantContext = Depends(require_permission("leads.change_status")),
    db: AsyncSession = Depends(get_db),
):
    leads = await services.bulk_change_status(
        db, lead_ids=payload.lead_ids, to_status=payload.status, actor_user_id=ctx.user_id
    )
    await db.commit()
    return [LeadResponse.from_model(lead) for lead in leads]


@router.post("/bulk/assign", response_model=list[LeadResponse])
async def bulk_assign(
    payload: BulkAssignRequest,
    ctx: TenantContext = Depends(require_permission("leads.assign")),
    db: AsyncSession = Depends(get_db),
):
    leads = await services.bulk_assign(
        db,
        lead_ids=payload.lead_ids,
        assigned_to_user_id=payload.assigned_to_user_id,
        actor_user_id=ctx.user_id,
    )
    await db.commit()
    return [LeadResponse.from_model(lead) for lead in leads]


@router.post("/bulk/tags", status_code=204)
async def bulk_add_tag(
    payload: BulkTagRequest,
    ctx: TenantContext = Depends(require_permission("leads.edit")),
    db: AsyncSession = Depends(get_db),
):
    await services.bulk_add_tag(
        db, lead_ids=payload.lead_ids, tag=payload.tag, actor_user_id=ctx.user_id
    )
    await db.commit()


@router.get("/{lead_id}", response_model=LeadDetailResponse)
async def get_lead(
    lead_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    lead = await leads_repo.get_lead_or_raise(db, lead_id)
    latest_score = await leads_repo.get_latest_score_for_lead(db, lead_id)
    opportunities = await leads_repo.list_opportunities_for_lead(db, lead_id)
    recommendations = await leads_repo.list_recommendations_for_lead(db, lead_id)
    notes = await leads_repo.list_notes(db, lead_id)
    tags = await leads_repo.list_tags(db, lead_id)
    status_history = await leads_repo.list_status_history(db, lead_id)
    assignment_history = await leads_repo.list_assignment_history(db, lead_id)
    duplicate_candidates = await businesses_repo.list_duplicate_candidates_for_business(
        db, lead.business_id
    )
    return LeadDetailResponse(
        lead=LeadResponse.from_model(lead),
        business_id=lead.business_id,
        latest_score=_to_score_response(latest_score) if latest_score else None,
        opportunities=[LeadOpportunityResponse.from_model(o) for o in opportunities],
        recommendations=[
            LeadRecommendationResponse(
                id=r.id,
                recommendation_type=r.recommendation_type,
                confidence=float(r.confidence),
                supporting_opportunity_ids=r.supporting_opportunity_ids,
                recommended_at=r.recommended_at,
            )
            for r in recommendations
        ],
        notes=[NoteResponse.from_model(n) for n in notes],
        tags=tags,
        status_history=[StatusHistoryResponse.from_model(h) for h in status_history],
        assignment_history=[AssignmentResponse.from_model(a) for a in assignment_history],
        duplicate_candidates=[
            DuplicateCandidateResponse.from_model(c) for c in duplicate_candidates
        ],
    )


@router.get("/{lead_id}/scores", response_model=list[LeadScoreResponse])
async def list_scores(
    lead_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    scores = await leads_repo.list_scores_for_lead(db, lead_id)
    return [_to_score_response(s) for s in scores]


@router.get("/{lead_id}/opportunities", response_model=list[LeadOpportunityResponse])
async def list_opportunities(
    lead_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    opportunities = await leads_repo.list_opportunities_for_lead(db, lead_id)
    return [LeadOpportunityResponse.from_model(o) for o in opportunities]


@router.get("/{lead_id}/recommendations", response_model=list[LeadRecommendationResponse])
async def list_recommendations(
    lead_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    recommendations = await leads_repo.list_recommendations_for_lead(db, lead_id)
    return [
        LeadRecommendationResponse(
            id=r.id,
            recommendation_type=r.recommendation_type,
            confidence=float(r.confidence),
            supporting_opportunity_ids=r.supporting_opportunity_ids,
            recommended_at=r.recommended_at,
        )
        for r in recommendations
    ]


@router.post("/{lead_id}/status", response_model=LeadResponse)
async def change_status(
    lead_id: uuid.UUID,
    payload: ChangeStatusRequest,
    ctx: TenantContext = Depends(require_permission("leads.change_status")),
    db: AsyncSession = Depends(get_db),
):
    lead = await services.change_status(
        db, lead_id=lead_id, to_status=payload.status, actor_user_id=ctx.user_id, note=payload.note
    )
    await db.commit()
    return LeadResponse.from_model(lead)


@router.get("/{lead_id}/status-history", response_model=list[StatusHistoryResponse])
async def list_status_history(
    lead_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    history = await leads_repo.list_status_history(db, lead_id)
    return [StatusHistoryResponse.from_model(h) for h in history]


@router.post("/{lead_id}/assign", response_model=LeadResponse)
async def assign_lead(
    lead_id: uuid.UUID,
    payload: AssignRequest,
    ctx: TenantContext = Depends(require_permission("leads.assign")),
    db: AsyncSession = Depends(get_db),
):
    lead = await services.assign_lead(
        db,
        lead_id=lead_id,
        assigned_to_user_id=payload.assigned_to_user_id,
        actor_user_id=ctx.user_id,
    )
    await db.commit()
    return LeadResponse.from_model(lead)


@router.post("/{lead_id}/unassign", response_model=LeadResponse)
async def unassign_lead(
    lead_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.assign")),
    db: AsyncSession = Depends(get_db),
):
    lead = await services.unassign_lead(db, lead_id=lead_id, actor_user_id=ctx.user_id)
    await db.commit()
    return LeadResponse.from_model(lead)


@router.get("/{lead_id}/assignment-history", response_model=list[AssignmentResponse])
async def list_assignment_history(
    lead_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    history = await leads_repo.list_assignment_history(db, lead_id)
    return [AssignmentResponse.from_model(a) for a in history]


@router.post("/{lead_id}/notes", response_model=NoteResponse)
async def add_note(
    lead_id: uuid.UUID,
    payload: AddNoteRequest,
    ctx: TenantContext = Depends(require_permission("leads.edit")),
    db: AsyncSession = Depends(get_db),
):
    note = await services.add_note(
        db, lead_id=lead_id, author_user_id=ctx.user_id, body=payload.body
    )
    await db.commit()
    return NoteResponse.from_model(note)


@router.get("/{lead_id}/notes", response_model=list[NoteResponse])
async def list_notes(
    lead_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    notes = await leads_repo.list_notes(db, lead_id)
    return [NoteResponse.from_model(n) for n in notes]


@router.post("/{lead_id}/tags", response_model=TagResponse)
async def add_tag(
    lead_id: uuid.UUID,
    payload: AddTagRequest,
    ctx: TenantContext = Depends(require_permission("leads.edit")),
    db: AsyncSession = Depends(get_db),
):
    entry = await services.add_tag(db, lead_id=lead_id, tag=payload.tag, actor_user_id=ctx.user_id)
    await db.commit()
    return TagResponse(tag=entry.tag)


@router.delete("/{lead_id}/tags/{tag}", status_code=204)
async def remove_tag(
    lead_id: uuid.UUID,
    tag: str,
    ctx: TenantContext = Depends(require_permission("leads.edit")),
    db: AsyncSession = Depends(get_db),
):
    await leads_repo.remove_tag(db, lead_id=lead_id, tag=tag)
    await db.commit()


@saved_views_router.get("", response_model=list[SavedViewResponse])
async def list_saved_views(
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    views = await leads_repo.list_saved_views(db, ctx.tenant_id)
    return [SavedViewResponse.from_model(v) for v in views]


@saved_views_router.post("", response_model=SavedViewResponse)
async def create_saved_view(
    payload: SavedViewCreateRequest,
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    view = await leads_repo.create_saved_view(
        db,
        tenant_id=ctx.tenant_id,
        name=payload.name,
        created_by_user_id=ctx.user_id,
        filters=payload.filters,
    )
    await db.commit()
    return SavedViewResponse.from_model(view)


@saved_views_router.delete("/{view_id}", status_code=204)
async def delete_saved_view(
    view_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    await services.delete_saved_view(
        db,
        view_id=view_id,
        actor_user_id=ctx.user_id,
        actor_can_edit="leads.edit" in ctx.permissions,
    )
    await db.commit()
