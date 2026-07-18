import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_client import enqueue_business_enrichment
from app.core.db import get_db
from app.dependencies import TenantContext, require_permission
from app.modules.businesses import dedup
from app.modules.businesses import repositories as businesses_repo
from app.modules.businesses.schemas import BusinessResponse
from app.modules.enrichment import repositories as enrichment_repo
from app.modules.enrichment.schemas import EnrichmentResponse, EvidenceResponse
from app.modules.leads import repositories as leads_repo
from app.modules.leads import scoring
from app.modules.leads.schemas import (
    DuplicateCandidateResponse,
    LeadOpportunityResponse,
    LeadRecommendationResponse,
    LeadResponse,
    LeadScoreResponse,
    MergeHistoryResponse,
    ScoreLeadResponse,
)

router = APIRouter(prefix="/businesses", tags=["businesses"])
duplicates_router = APIRouter(prefix="/duplicate-candidates", tags=["businesses"])
merges_router = APIRouter(prefix="/merges", tags=["businesses"])


def _to_enrichment_response(enrichment) -> EnrichmentResponse:
    return EnrichmentResponse(
        id=enrichment.id,
        business_id=enrichment.business_id,
        status=enrichment.status,
        pages_crawled=enrichment.pages_crawled,
        started_at=enrichment.started_at,
        completed_at=enrichment.completed_at,
        error_message=enrichment.error_message,
    )


@router.get("/{business_id}", response_model=BusinessResponse)
async def get_business(
    business_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    business = await businesses_repo.get_business_or_raise(db, business_id)
    return BusinessResponse.from_model(business)


@router.post("/{business_id}/enrich", response_model=EnrichmentResponse)
async def trigger_enrichment(
    business_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.enrich")),
    db: AsyncSession = Depends(get_db),
):
    # Confirms the business exists (and belongs to this tenant, via RLS)
    # before creating an enrichment row for it.
    await businesses_repo.get_business_or_raise(db, business_id)
    enrichment = await enrichment_repo.create_enrichment(
        db, tenant_id=ctx.tenant_id, business_id=business_id
    )
    # Commit before enqueueing: the worker must never be able to consume
    # the Celery message before the enrichment row it needs is visible -
    # same rule as campaigns.routes.launch_campaign.
    await db.commit()
    enqueue_business_enrichment(str(enrichment.id))
    return _to_enrichment_response(enrichment)


@router.get("/{business_id}/enrichment", response_model=EnrichmentResponse | None)
async def get_latest_enrichment(
    business_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    enrichment = await enrichment_repo.get_latest_enrichment_for_business(db, business_id)
    return _to_enrichment_response(enrichment) if enrichment else None


@router.get("/{business_id}/evidence", response_model=list[EvidenceResponse])
async def list_evidence(
    business_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    evidence = await enrichment_repo.list_evidence_for_business(db, business_id)
    return [
        EvidenceResponse(
            id=e.id,
            detector_type=e.detector_type,
            source_url=e.source_url,
            structured_result=e.structured_result,
            confidence=float(e.confidence),
            supporting_snippet=e.supporting_snippet,
            collected_at=e.collected_at,
        )
        for e in evidence
    ]


@router.post("/{business_id}/score", response_model=ScoreLeadResponse)
async def score_business(
    business_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.score")),
    db: AsyncSession = Depends(get_db),
):
    # Pure computation over already-persisted data (no crawl, no external
    # call) - unlike enrichment, this runs synchronously in-request rather
    # than as a background Celery task; see docs/adr/0013.
    lead, score, opportunities, recommendations = await scoring.score_lead(db, business_id)
    await db.commit()
    return ScoreLeadResponse(
        lead=LeadResponse.from_model(lead),
        score=LeadScoreResponse(
            id=score["id"],
            algorithm_version=score["algorithm_version"],
            total_score=score["total_score"],
            max_score=score["max_score"],
            factors=score["factors"],
            calculated_at=score["calculated_at"],
        ),
        opportunities=[LeadOpportunityResponse.from_model(o) for o in opportunities],
        recommendations=[LeadRecommendationResponse(**r) for r in recommendations],
    )


@router.get("/{business_id}/lead", response_model=LeadResponse | None)
async def get_lead_for_business(
    business_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    lead = await leads_repo.get_lead_for_business(db, business_id)
    return LeadResponse.from_model(lead) if lead else None


@router.get("/{business_id}/duplicates", response_model=list[DuplicateCandidateResponse])
async def list_duplicates_for_business(
    business_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    candidates = await businesses_repo.list_duplicate_candidates_for_business(db, business_id)
    return [DuplicateCandidateResponse.from_model(c) for c in candidates]


@router.get("/{business_id}/merge-history", response_model=list[MergeHistoryResponse])
async def list_merge_history_for_business(
    business_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    history = await businesses_repo.list_merge_history_for_business(db, business_id)
    return [MergeHistoryResponse.from_model(h) for h in history]


@duplicates_router.get("", response_model=list[DuplicateCandidateResponse])
async def list_duplicate_candidates(
    status: str = "pending",
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    candidates = await businesses_repo.list_duplicate_candidates(
        db, tenant_id=ctx.tenant_id, status=status
    )
    return [DuplicateCandidateResponse.from_model(c) for c in candidates]


@duplicates_router.post("/{candidate_id}/confirm", response_model=MergeHistoryResponse)
async def confirm_duplicate_candidate(
    candidate_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.edit")),
    db: AsyncSession = Depends(get_db),
):
    merge_history = await dedup.confirm_candidate(
        db, candidate_id=candidate_id, actor_user_id=ctx.user_id
    )
    await db.commit()
    return MergeHistoryResponse.from_model(merge_history)


@duplicates_router.post("/{candidate_id}/reject", response_model=DuplicateCandidateResponse)
async def reject_duplicate_candidate(
    candidate_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.edit")),
    db: AsyncSession = Depends(get_db),
):
    candidate = await dedup.reject_candidate(
        db, candidate_id=candidate_id, actor_user_id=ctx.user_id
    )
    await db.commit()
    return DuplicateCandidateResponse.from_model(candidate)


@merges_router.post("/{merge_history_id}/undo", response_model=MergeHistoryResponse)
async def undo_merge(
    merge_history_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.edit")),
    db: AsyncSession = Depends(get_db),
):
    merge_history = await dedup.undo_merge(
        db, merge_history_id=merge_history_id, actor_user_id=ctx.user_id
    )
    await db.commit()
    return MergeHistoryResponse.from_model(merge_history)
