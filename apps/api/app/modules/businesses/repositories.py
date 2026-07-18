import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.modules.businesses.models import Business, BusinessSourceRecord

# Fields copied directly from a connector's BusinessRecord onto Business at
# discovery time. `email` is deliberately excluded - see models.py.
_DISCOVERY_FIELDS = (
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
    stmt = (
        select(Business)
        .join(BusinessSourceRecord, BusinessSourceRecord.business_id == Business.id)
        .where(BusinessSourceRecord.campaign_id == campaign_id)
        .distinct()
        .order_by(Business.name)
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
    discovery-owned fields (`_DISCOVERY_FIELDS`) on every (re)discovery -
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
    for field_name in _DISCOVERY_FIELDS:
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
        business.canonical_domain = _canonical_domain(business.website)

    return business


def _canonical_domain(url: str) -> str | None:
    from urllib.parse import urlparse

    try:
        netloc = urlparse(url if "//" in url else f"//{url}").netloc.lower()
    except ValueError:
        return None
    return netloc.removeprefix("www.") or None
