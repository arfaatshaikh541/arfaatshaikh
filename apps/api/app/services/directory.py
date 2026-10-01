"""Directory engine: search with filters and distance, community suggestions, reports, moderation, duplicates."""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.models.content_contract import DataSet, DirectoryListing, DirectoryReport, PlatformAuditEvent
from app.models.identity import User
from app.services.data_contracts import DirectoryListingInput, haversine_km


def _close(a: DirectoryListing, b: DirectoryListing) -> bool:
    """Same place: coordinates unknown on either side, or within the duplicate radius."""
    if a.latitude is None or a.longitude is None or b.latitude is None or b.longitude is None:
        return True
    return haversine_km(a.latitude, a.longitude, b.latitude, b.longitude) <= DUPLICATE_RADIUS_KM


PAGE_MAX = 50
DUPLICATE_RADIUS_KM = 0.2



def public_filter(now: datetime | None = None):
    """Visible to everyone: published, not a duplicate, not expired (jobs, events), and, if imported, from an enabled published dataset.

    Expiry is evaluated on every read, so a closed job or a finished event disappears without any background task.
    """
    now = now or datetime.now(UTC)
    return and_(
        DirectoryListing.status == "published",
        DirectoryListing.duplicate_of_id.is_(None),
        or_(DirectoryListing.expires_at.is_(None), DirectoryListing.expires_at > now),
        or_(DirectoryListing.listing_type != "event", func.coalesce(DirectoryListing.ends_at, DirectoryListing.starts_at + timedelta(hours=6)) > now),
        or_(DirectoryListing.dataset_id.is_(None),
            DirectoryListing.dataset_id.in_(select(DataSet.id).where(DataSet.publication_status == "published", DataSet.enabled.is_(True)))),
    )


def listing_view(listing: DirectoryListing, distance_km: float | None = None) -> dict:
    return {
        "id": str(listing.id), "type": listing.listing_type, "name": listing.name, "arabic_name": listing.arabic_name,
        "description": listing.description, "category": listing.category, "tags": listing.tags, "address": listing.address,
        "city": listing.city, "region": listing.region, "country": listing.country, "latitude": listing.latitude, "longitude": listing.longitude,
        "phone": listing.phone, "email": listing.email, "website": listing.website,
        "starts_at": listing.starts_at.isoformat() if listing.starts_at else None, "ends_at": listing.ends_at.isoformat() if listing.ends_at else None,
        "expires_at": listing.expires_at.isoformat() if listing.expires_at else None, "posted_at": listing.posted_at.isoformat() if listing.posted_at else None,
        "attributes": listing.attributes or {},
        "source": listing.source, "source_url": listing.source_url, "license": listing.license, "provenance": listing.provenance,
        "last_verified": listing.last_verified.isoformat() if listing.last_verified else None,
        "verification_status": listing.verification_status, "verified_at": listing.verified_at.isoformat() if listing.verified_at else None,
        "last_updated": (listing.source_updated_at.isoformat() if listing.source_updated_at else listing.updated_at.date().isoformat()),
        "distance_km": round(distance_km, 2) if distance_km is not None else None,
    }


async def search_listings(db: AsyncSession, *, q: str | None, listing_type: str | None, category: str | None, country: str | None,
                          city: str | None, near: tuple[float, float] | None, radius_km: float | None, verified_only: bool,
                          page: int, page_size: int) -> dict:
    page_size = max(1, min(page_size, PAGE_MAX))
    conditions = [public_filter()]
    if listing_type:
        conditions.append(DirectoryListing.listing_type == listing_type)
    if category:
        conditions.append(func.lower(DirectoryListing.category) == category.lower())
    if country:
        conditions.append(DirectoryListing.country == country.upper())
    if city:
        conditions.append(func.lower(DirectoryListing.city) == city.lower())
    if verified_only:
        conditions.append(DirectoryListing.verification_status == "verified")
    if q and q.strip():
        document = func.to_tsvector("simple", DirectoryListing.name + " " + func.coalesce(DirectoryListing.arabic_name, "") + " " +
                                    func.coalesce(DirectoryListing.description, "") + " " + func.coalesce(DirectoryListing.city, ""))
        conditions.append(document.op("@@")(func.plainto_tsquery("simple", q.strip())))
    if near and radius_km:
        lat, lon = near
        dlat = radius_km / 111.0
        dlon = radius_km / max(111.0 * math.cos(math.radians(lat)), 1e-6)
        conditions.append(and_(DirectoryListing.latitude.between(lat - dlat, lat + dlat), DirectoryListing.longitude.between(lon - dlon, lon + dlon)))
    total = await db.scalar(select(func.count()).select_from(DirectoryListing).where(*conditions)) or 0
    order = [case((DirectoryListing.verification_status == "verified", 0), else_=1), DirectoryListing.name]
    rows = (await db.scalars(select(DirectoryListing).where(*conditions).order_by(*order).limit(page_size * 3 if near else page_size).offset(0 if near else (page - 1) * page_size))).all()
    items = [listing_view(row, haversine_km(near[0], near[1], row.latitude, row.longitude) if near and row.latitude is not None and row.longitude is not None else None) for row in rows]
    if near:
        if radius_km:
            items = [item for item in items if item["distance_km"] is not None and item["distance_km"] <= radius_km]
        items.sort(key=lambda item: (item["distance_km"] is None, item["distance_km"] or 0))
        items = items[(page - 1) * page_size: page * page_size]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


class DirectoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def audit(self, actor: User | None, action: str, target_id: UUID | None, meta: dict) -> None:
        self.db.add(PlatformAuditEvent(actor_user_id=actor.id if actor else None, action=action, target_type="directory_listing", target_id=target_id,
                                       metadata_json=json.loads(json.dumps(meta, default=str, ensure_ascii=False)), created_at=datetime.now(UTC)))

    async def suggest(self, payload: DirectoryListingInput, user: User) -> DirectoryListing:
        pending = await self.db.scalar(select(func.count()).select_from(DirectoryListing).where(
            DirectoryListing.submitted_by_user_id == user.id, DirectoryListing.status == "pending"))
        if (pending or 0) >= 20:
            raise ApplicationError("too_many_pending", "You already have 20 listings awaiting review.", 429)
        values = payload.model_dump(exclude={"external_key"})
        listing = DirectoryListing(dataset_id=None, external_key=None, status="pending", verification_status="unverified",
                                   submitted_by_user_id=user.id, dedupe_key=payload.key, **values)
        self.db.add(listing)
        await self.db.flush()
        await self._link_duplicate(listing)
        await self.audit(user, "directory.suggested", listing.id, {"type": listing.listing_type})
        return listing

    async def _link_duplicate(self, listing: DirectoryListing) -> UUID | None:
        stmt = select(DirectoryListing).where(DirectoryListing.dedupe_key == listing.dedupe_key, DirectoryListing.id != listing.id,
                                              DirectoryListing.duplicate_of_id.is_(None), DirectoryListing.status.in_(("pending", "published"))).order_by(DirectoryListing.created_at).limit(5)
        for other in (await self.db.scalars(stmt)).all():
            if _close(listing, other):
                if other.created_at <= listing.created_at or other.status == "published":
                    listing.duplicate_of_id = other.id
                    return other.id
        return None

    async def scan_duplicates(self, actor: User) -> int:
        linked = 0
        rows = (await self.db.scalars(select(DirectoryListing).where(DirectoryListing.duplicate_of_id.is_(None), DirectoryListing.status.in_(("pending", "published"))).order_by(DirectoryListing.created_at))).all()
        by_key: dict[str, list[DirectoryListing]] = {}
        for row in rows:
            by_key.setdefault(row.dedupe_key, []).append(row)
        for group in by_key.values():
            keeper, *rest = group
            for other in rest:
                if _close(keeper, other):
                    other.duplicate_of_id = keeper.id
                    linked += 1
        await self.audit(actor, "directory.duplicate_scan", None, {"linked": linked})
        return linked

    async def report(self, listing_id: UUID, reason: str, details: str | None, user: User | None) -> DirectoryReport:
        listing = await self.db.get(DirectoryListing, listing_id)
        if listing is None or listing.status != "published":
            raise ApplicationError("listing_not_found", "Listing not found.", 404)
        report = DirectoryReport(listing_id=listing_id, reporter_user_id=user.id if user else None, reason=reason, details=(details or None))
        self.db.add(report)
        await self.db.flush()
        return report

    async def moderate(self, listing_id: UUID, action: str, actor: User, note: str | None) -> DirectoryListing:
        listing = await self.db.get(DirectoryListing, listing_id)
        if listing is None:
            raise ApplicationError("listing_not_found", "Listing not found.", 404)
        now = datetime.now(UTC)
        if action == "approve":
            listing.status = "published"
        elif action == "reject":
            listing.status = "rejected"
        elif action == "hide":
            listing.status = "hidden"
        elif action == "verify":
            if listing.status != "published":
                raise ApplicationError("not_published", "Only a published listing can be verified.", 409)
            listing.verification_status, listing.verified_by_user_id, listing.verified_at = "verified", actor.id, now
        elif action == "unverify":
            listing.verification_status, listing.verified_by_user_id, listing.verified_at = "unverified", None, None
        elif action == "suspend":
            listing.verification_status, listing.status = "suspended", "hidden"
        else:
            raise ApplicationError("invalid_action", "Unknown moderation action.", 422)
        listing.moderation_note = note
        await self.audit(actor, f"directory.{action}", listing.id, {"note": note})
        return listing

    async def resolve_report(self, report_id: UUID, outcome: str, actor: User, note: str | None, hide_listing: bool = False) -> DirectoryReport:
        report = await self.db.get(DirectoryReport, report_id)
        if report is None:
            raise ApplicationError("report_not_found", "Report not found.", 404)
        if outcome not in {"actioned", "dismissed"}:
            raise ApplicationError("invalid_outcome", "Outcome must be actioned or dismissed.", 422)
        report.status, report.resolved_by_user_id, report.resolution_note, report.resolved_at = outcome, actor.id, note, datetime.now(UTC)
        if hide_listing and outcome == "actioned":
            listing = await self.db.get(DirectoryListing, report.listing_id)
            if listing:
                listing.status = "hidden"
        await self.audit(actor, f"directory.report_{outcome}", report.listing_id, {"report": str(report.id), "note": note})
        return report
