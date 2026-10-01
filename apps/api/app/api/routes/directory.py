"""Directory engine API: public search/detail, signed-in suggestions and reports, administrator moderation.

Nothing is pre-populated. Imported datasets appear only while their dataset is published and enabled; community
suggestions stay `pending` until a moderator approves them.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.dependencies.auth import DbSession, get_current_user, require_csrf
from app.api.dependencies.platform_admin import require_platform_administrator
from app.core.config import get_settings
from app.core.errors import ApplicationError
from app.core.rate_limit import rate_limiter
from app.models.content_contract import LISTING_TYPES, DirectoryListing, DirectoryReport
from app.models.identity import Session, User
from app.services.data_contracts import DirectoryListingInput
from app.services.directory import DirectoryService, listing_view, public_filter, search_listings

router = APIRouter(prefix="/directory", tags=["directory"])


@router.get("/listings")
async def listings(request: Request, db: DbSession, q: Annotated[str | None, Query(max_length=200)] = None, type: Annotated[str | None, Query(max_length=24)] = None,
                   category: Annotated[str | None, Query(max_length=120)] = None, country: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
                   city: Annotated[str | None, Query(max_length=120)] = None, lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
                   lon: Annotated[float | None, Query(ge=-180, le=180)] = None, radius_km: Annotated[float | None, Query(gt=0, le=500)] = None,
                   verified_only: bool = False, page: Annotated[int, Query(ge=1, le=10000)] = 1, page_size: Annotated[int, Query(ge=1, le=50)] = 20):
    await rate_limiter.check(request, "directory", max(get_settings().auth_rate_limit * 6, 60), 60)
    if type and type not in LISTING_TYPES:
        raise ApplicationError("invalid_type", "Unknown listing type.", 422)
    if (lat is None) != (lon is None) or (radius_km is not None and lat is None):
        raise ApplicationError("invalid_location", "Give lat and lon together; radius_km needs them.", 422)
    near = (lat, lon) if lat is not None and lon is not None else None
    return await search_listings(db, q=q, listing_type=type, category=category, country=country, city=city, near=near, radius_km=radius_km,
                                 verified_only=verified_only, page=page, page_size=page_size)


@router.get("/summary")
async def summary(db: DbSession):
    """Counts per listing type, so the UI can say honestly which directories are empty."""
    counts = (await db.execute(select(DirectoryListing.listing_type, func.count()).where(public_filter()).group_by(DirectoryListing.listing_type))).all()
    rows: dict[str, int] = {kind: int(total) for kind, total in counts}
    return {"types": [{"type": t, "count": rows.get(t, 0)} for t in LISTING_TYPES]}


@router.get("/coverage")
async def coverage(db: DbSession):
    """Which countries have data for which listing type, so the UI never implies global coverage."""
    rows = (await db.execute(select(DirectoryListing.country, DirectoryListing.listing_type, func.count()).where(public_filter()).group_by(DirectoryListing.country, DirectoryListing.listing_type)
                             .order_by(DirectoryListing.listing_type, DirectoryListing.country))).all()
    items = [{"country": country or "unknown", "type": kind, "count": int(total)} for country, kind, total in rows]
    by_type: dict[str, list[str]] = {}
    for item in items:
        by_type.setdefault(item["type"], []).append(item["country"])
    return {"items": items, "countries_by_type": by_type,
            "statement": "Listings exist only for the countries shown. Any other country has no data yet; absence of a listing does not mean absence of a mosque or service."}


@router.get("/listings/{listing_id}")
async def listing_detail(listing_id: UUID, db: DbSession):
    row = await db.scalar(select(DirectoryListing).where(DirectoryListing.id == listing_id, public_filter()))
    if row is None:
        raise ApplicationError("listing_not_found", "Listing not found.", 404)
    return listing_view(row)




@router.post("/listings", status_code=201)
async def suggest_listing(payload: DirectoryListingInput, db: DbSession, user: Annotated[User, Depends(get_current_user)], _: Annotated[Session, Depends(require_csrf)]):
    listing = await DirectoryService(db).suggest(payload, user)
    await db.commit()
    return {"id": str(listing.id), "status": listing.status, "message": "Thank you. Your suggestion is waiting for moderator review."}


class ReportPayload(BaseModel):
    reason: str = Field(pattern=r"^(incorrect|closed|duplicate|offensive|fraud|other)$")
    details: str | None = Field(default=None, max_length=2000)


@router.post("/listings/{listing_id}/report", status_code=201)
async def report_listing(listing_id: UUID, payload: ReportPayload, request: Request, db: DbSession, user: Annotated[User, Depends(get_current_user)], _: Annotated[Session, Depends(require_csrf)]):
    await rate_limiter.check(request, "directory-report", 20, 3600)
    report = await DirectoryService(db).report(listing_id, payload.reason, payload.details, user)
    await db.commit()
    return {"id": str(report.id), "status": report.status}


# ------------------------------------------------------------------ administrators
class ModeratePayload(BaseModel):
    action: str = Field(pattern=r"^(approve|reject|hide|verify|unverify|suspend)$")
    note: str | None = Field(default=None, max_length=1000)


@router.get("/admin/queue")
async def moderation_queue(db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], status: str = "pending", page: Annotated[int, Query(ge=1)] = 1):
    if status not in {"pending", "published", "hidden", "rejected"}:
        raise ApplicationError("invalid_status", "Unknown status.", 422)
    rows = (await db.scalars(select(DirectoryListing).where(DirectoryListing.status == status).order_by(DirectoryListing.created_at).limit(50).offset((page - 1) * 50))).all()
    return {"items": [{**listing_view(r), "status": r.status, "duplicate_of": str(r.duplicate_of_id) if r.duplicate_of_id else None, "moderation_note": r.moderation_note,
                       "submitted_by": str(r.submitted_by_user_id) if r.submitted_by_user_id else None, "provenance": r.provenance} for r in rows]}


@router.post("/admin/listings/{listing_id}/moderate")
async def moderate(listing_id: UUID, payload: ModeratePayload, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    listing = await DirectoryService(db).moderate(listing_id, payload.action, admin, payload.note)
    await db.commit()
    return {"id": str(listing.id), "status": listing.status, "verification_status": listing.verification_status}


@router.get("/admin/reports")
async def reports(db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], status: str = "open"):
    rows = (await db.scalars(select(DirectoryReport).where(DirectoryReport.status == status).order_by(DirectoryReport.created_at).limit(100))).all()
    return {"items": [{"id": str(r.id), "listing_id": str(r.listing_id), "reason": r.reason, "details": r.details, "status": r.status, "created_at": r.created_at.isoformat()} for r in rows]}


class ResolvePayload(BaseModel):
    outcome: str = Field(pattern=r"^(actioned|dismissed)$")
    note: str | None = Field(default=None, max_length=1000)
    hide_listing: bool = False


@router.post("/admin/reports/{report_id}/resolve")
async def resolve(report_id: UUID, payload: ResolvePayload, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    report = await DirectoryService(db).resolve_report(report_id, payload.outcome, admin, payload.note, payload.hide_listing)
    await db.commit()
    return {"id": str(report.id), "status": report.status}


@router.post("/admin/duplicates/scan")
async def scan_duplicates(db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    linked = await DirectoryService(db).scan_duplicates(admin)
    await db.commit()
    return {"linked": linked}
