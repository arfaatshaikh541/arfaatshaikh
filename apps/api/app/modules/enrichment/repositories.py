import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.modules.enrichment.models import BusinessEnrichment, EnrichmentEvidence


async def create_enrichment(
    session: AsyncSession, *, tenant_id: uuid.UUID, business_id: uuid.UUID
) -> BusinessEnrichment:
    enrichment = BusinessEnrichment(tenant_id=tenant_id, business_id=business_id, status="pending")
    session.add(enrichment)
    await session.flush()
    return enrichment


async def get_enrichment(
    session: AsyncSession, enrichment_id: uuid.UUID
) -> BusinessEnrichment | None:
    stmt = select(BusinessEnrichment).where(BusinessEnrichment.id == enrichment_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_enrichment_or_raise(
    session: AsyncSession, enrichment_id: uuid.UUID
) -> BusinessEnrichment:
    enrichment = await get_enrichment(session, enrichment_id)
    if enrichment is None:
        raise ResourceNotFoundError("Enrichment run not found.")
    return enrichment


async def get_latest_enrichment_for_business(
    session: AsyncSession, business_id: uuid.UUID
) -> BusinessEnrichment | None:
    stmt = (
        select(BusinessEnrichment)
        .where(BusinessEnrichment.business_id == business_id)
        .order_by(BusinessEnrichment.created_at.desc())
    )
    return (await session.execute(stmt)).scalars().first()


async def record_evidence(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    business_id: uuid.UUID,
    enrichment_id: uuid.UUID,
    detector_type: str,
    source_url: str,
    structured_result: dict,
    confidence: float,
    collected_at: datetime,
    supporting_snippet: str | None = None,
) -> EnrichmentEvidence:
    evidence = EnrichmentEvidence(
        tenant_id=tenant_id,
        business_id=business_id,
        enrichment_id=enrichment_id,
        detector_type=detector_type,
        source_url=source_url,
        structured_result=structured_result,
        confidence=confidence,
        supporting_snippet=supporting_snippet,
        collected_at=collected_at,
    )
    session.add(evidence)
    return evidence


async def list_evidence_for_business(
    session: AsyncSession, business_id: uuid.UUID
) -> list[EnrichmentEvidence]:
    stmt = (
        select(EnrichmentEvidence)
        .where(EnrichmentEvidence.business_id == business_id)
        .order_by(EnrichmentEvidence.collected_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_evidence_for_enrichment(
    session: AsyncSession, enrichment_id: uuid.UUID
) -> list[EnrichmentEvidence]:
    stmt = select(EnrichmentEvidence).where(EnrichmentEvidence.enrichment_id == enrichment_id)
    return list((await session.execute(stmt)).scalars().all())


# WhatsApp/social-profile detector types (see worker.crawler.detectors) -
# the export's WhatsApp/Facebook/Instagram/LinkedIn URL columns
# (Milestone 7) read exactly these, never anything inferred.
SOCIAL_DETECTOR_TYPES = ("whatsapp", "social_facebook", "social_instagram", "social_linkedin")


async def list_social_evidence_for_businesses(
    session: AsyncSession, business_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[str, EnrichmentEvidence]]:
    """{business_id: {detector_type: EnrichmentEvidence}} - only from each
    business's most recent *completed* enrichment run, batched for export
    generation the same way `businesses.repositories.
    list_latest_source_records_for_businesses` batches source records."""
    if not business_ids:
        return {}
    ranked = (
        select(
            BusinessEnrichment.id,
            BusinessEnrichment.business_id,
            func.row_number()
            .over(
                partition_by=BusinessEnrichment.business_id,
                order_by=BusinessEnrichment.created_at.desc(),
            )
            .label("rn"),
        ).where(
            BusinessEnrichment.business_id.in_(business_ids),
            BusinessEnrichment.status == "completed",
        )
    ).subquery()
    latest_enrichment_ids = select(ranked.c.id).where(ranked.c.rn == 1)

    stmt = select(EnrichmentEvidence).where(
        EnrichmentEvidence.enrichment_id.in_(latest_enrichment_ids),
        EnrichmentEvidence.detector_type.in_(SOCIAL_DETECTOR_TYPES),
    )
    result: dict[uuid.UUID, dict[str, EnrichmentEvidence]] = {}
    for evidence in (await session.execute(stmt)).scalars().all():
        result.setdefault(evidence.business_id, {})[evidence.detector_type] = evidence
    return result
