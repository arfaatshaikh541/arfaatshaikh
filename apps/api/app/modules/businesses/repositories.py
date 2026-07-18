import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.modules.businesses.models import (
    Business,
    BusinessDuplicateCandidate,
    BusinessMergeHistory,
    BusinessSourceRecord,
)
from app.modules.businesses.normalize import canonical_domain, normalize_phone

# Fields copied directly from a connector's BusinessRecord onto Business at
# discovery time. `email` is deliberately excluded - see models.py.
DISCOVERY_FIELDS = (
    "name",
    "category",
    "address",
    "country",
    "region",
    "city",
    "area",
    "latitude",
    "longitude",
    "phone",
    "website",
    "google_maps_url",
    "rating",
    "review_count",
    "business_status",
)


async def get_business(session: AsyncSession, business_id: uuid.UUID) -> Business | None:
    stmt = select(Business).where(Business.id == business_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_business_or_raise(session: AsyncSession, business_id: uuid.UUID) -> Business:
    business = await get_business(session, business_id)
    if business is None:
        raise ResourceNotFoundError("Business not found.")
    return business


async def get_source_record_by_native_id(
    session: AsyncSession, *, tenant_id: uuid.UUID, source: str, source_native_id: str
) -> BusinessSourceRecord | None:
    stmt = select(BusinessSourceRecord).where(
        BusinessSourceRecord.tenant_id == tenant_id,
        BusinessSourceRecord.source == source,
        BusinessSourceRecord.source_native_id == source_native_id,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_businesses_for_campaign(
    session: AsyncSession, campaign_id: uuid.UUID
) -> list[Business]:
    """Only canonical (non-merged-away) businesses - a business that lost a
    Milestone 5 dedup merge is still reachable via `get_business` (its
    history is never deleted), but it should stop appearing in normal
    listings once `merged_into_id` points somewhere else."""
    stmt = (
        select(Business)
        .join(BusinessSourceRecord, BusinessSourceRecord.business_id == Business.id)
        .where(BusinessSourceRecord.campaign_id == campaign_id, Business.merged_into_id.is_(None))
        .distinct()
        .order_by(Business.name)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_latest_campaign_id_for_business(
    session: AsyncSession, business_id: uuid.UUID
) -> uuid.UUID | None:
    """The most recently (re)discovering campaign - used by lead scoring
    to compare a business against the filter that originally targeted it
    (category/location match). A merge (Milestone 5) can reassign source
    records from more than one original campaign onto the same winner
    Business, so this deliberately picks the most recent one rather than
    an arbitrary one."""
    stmt = (
        select(BusinessSourceRecord.campaign_id)
        .where(
            BusinessSourceRecord.business_id == business_id,
            BusinessSourceRecord.campaign_id.is_not(None),
        )
        .order_by(BusinessSourceRecord.collected_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_duplicate_candidate(
    session: AsyncSession, candidate_id: uuid.UUID
) -> BusinessDuplicateCandidate | None:
    stmt = select(BusinessDuplicateCandidate).where(BusinessDuplicateCandidate.id == candidate_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_duplicate_candidate_or_raise(
    session: AsyncSession, candidate_id: uuid.UUID
) -> BusinessDuplicateCandidate:
    candidate = await get_duplicate_candidate(session, candidate_id)
    if candidate is None:
        raise ResourceNotFoundError("Duplicate candidate not found.")
    return candidate


async def get_duplicate_candidate_by_pair(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    business_id_a: uuid.UUID,
    business_id_b: uuid.UUID,
) -> BusinessDuplicateCandidate | None:
    stmt = select(BusinessDuplicateCandidate).where(
        BusinessDuplicateCandidate.tenant_id == tenant_id,
        BusinessDuplicateCandidate.business_id_a == business_id_a,
        BusinessDuplicateCandidate.business_id_b == business_id_b,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_duplicate_candidates_for_business(
    session: AsyncSession, business_id: uuid.UUID
) -> list[BusinessDuplicateCandidate]:
    stmt = (
        select(BusinessDuplicateCandidate)
        .where(
            (BusinessDuplicateCandidate.business_id_a == business_id)
            | (BusinessDuplicateCandidate.business_id_b == business_id)
        )
        .order_by(BusinessDuplicateCandidate.confidence.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_duplicate_candidates(
    session: AsyncSession, *, tenant_id: uuid.UUID, status: str | None = "pending"
) -> list[BusinessDuplicateCandidate]:
    stmt = select(BusinessDuplicateCandidate).where(
        BusinessDuplicateCandidate.tenant_id == tenant_id
    )
    if status is not None:
        stmt = stmt.where(BusinessDuplicateCandidate.status == status)
    stmt = stmt.order_by(BusinessDuplicateCandidate.confidence.desc())
    return list((await session.execute(stmt)).scalars().all())


async def get_merge_history(
    session: AsyncSession, merge_history_id: uuid.UUID
) -> BusinessMergeHistory | None:
    stmt = select(BusinessMergeHistory).where(BusinessMergeHistory.id == merge_history_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_merge_history_or_raise(
    session: AsyncSession, merge_history_id: uuid.UUID
) -> BusinessMergeHistory:
    merge_history = await get_merge_history(session, merge_history_id)
    if merge_history is None:
        raise ResourceNotFoundError("Merge history record not found.")
    return merge_history


async def list_merge_history_for_business(
    session: AsyncSession, business_id: uuid.UUID
) -> list[BusinessMergeHistory]:
    stmt = (
        select(BusinessMergeHistory)
        .where(
            (BusinessMergeHistory.winner_business_id == business_id)
            | (BusinessMergeHistory.loser_business_id == business_id)
        )
        .order_by(BusinessMergeHistory.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def upsert_business_from_discovery(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    campaign_id: uuid.UUID,
    record: dict,
) -> Business:
    """Creates or refreshes a Business from one connector search result.

    A connector's own current response is treated as authoritative for the
    discovery-owned fields (`DISCOVERY_FIELDS`) on every (re)discovery -
    there is no cross-source merge logic yet (that is Milestone 5's
    deduplication step); this only ever writes fields sourced from the
    *same* source_native_id, never blends data from a different source
    into an existing Business. `email` (enrichment-owned) is never
    touched here.
    """
    source = record["source"]
    source_native_id = record["source_native_id"]
    now = datetime.now(UTC)

    existing_source_record = await get_source_record_by_native_id(
        session, tenant_id=tenant_id, source=source, source_native_id=source_native_id
    )

    if existing_source_record is not None:
        existing_source_record.campaign_id = campaign_id
        existing_source_record.source_url = record.get("source_url")
        existing_source_record.collected_at = now
        existing_source_record.raw_snapshot = record
        business = await get_business_or_raise(session, existing_source_record.business_id)
    else:
        business = Business(tenant_id=tenant_id, name=record["name"])
        session.add(business)
        await session.flush()
        source_record = BusinessSourceRecord(
            tenant_id=tenant_id,
            business_id=business.id,
            campaign_id=campaign_id,
            source=source,
            source_native_id=source_native_id,
            source_url=record.get("source_url"),
            collected_at=now,
            raw_snapshot=record,
        )
        session.add(source_record)
        await session.flush()
        existing_source_record = source_record

    provenance = dict(business.field_provenance)
    for field_name in DISCOVERY_FIELDS:
        value = record.get(field_name)
        if value is None:
            continue
        setattr(business, field_name, value)
        provenance[field_name] = {
            "source": source,
            "source_record_id": str(existing_source_record.id),
            "confidence": 1.0,
            "collected_at": now.isoformat(),
        }
    business.field_provenance = provenance

    if source == "google_places":
        business.google_place_id = source_native_id
    if business.website:
        business.canonical_domain = canonical_domain(business.website)
    if business.phone:
        business.normalized_phone = normalize_phone(business.phone)

    return business
