import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.dependencies import TenantContext, require_permission
from app.modules.leads import repositories as leads_repo
from app.modules.leads.schemas import (
    LeadOpportunityResponse,
    LeadRecommendationResponse,
    LeadResponse,
    LeadScoreResponse,
)

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    lead = await leads_repo.get_lead_or_raise(db, lead_id)
    return LeadResponse.from_model(lead)


@router.get("/{lead_id}/scores", response_model=list[LeadScoreResponse])
async def list_scores(
    lead_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    scores = await leads_repo.list_scores_for_lead(db, lead_id)
    return [
        LeadScoreResponse(
            id=s.id,
            algorithm_version=s.algorithm_version,
            total_score=float(s.total_score),
            max_score=float(s.max_score),
            factors=s.factors,
            calculated_at=s.calculated_at,
        )
        for s in scores
    ]


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
