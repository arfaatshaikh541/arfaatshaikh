import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_client import enqueue_business_enrichment
from app.core.db import get_db
from app.dependencies import TenantContext, require_permission
from app.modules.businesses import repositories as businesses_repo
from app.modules.businesses.schemas import BusinessResponse
from app.modules.enrichment import repositories as enrichment_repo
from app.modules.enrichment.schemas import EnrichmentResponse, EvidenceResponse

router = APIRouter(prefix="/businesses", tags=["businesses"])


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
