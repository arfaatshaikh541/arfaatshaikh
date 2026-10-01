from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.api.dependencies.auth import DbSession
from app.core.config import get_settings
from app.core.rate_limit import rate_limiter
from app.services.unified_search import ALL_TYPES, unified_search

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search(request: Request, db: DbSession, q: Annotated[str, Query(min_length=2, max_length=200)], types: Annotated[str | None, Query(max_length=300)] = None,
                 limit: Annotated[int, Query(ge=1, le=20)] = 8):
    """Unified search over published, verified content. Each result names its type, source and licence."""
    await rate_limiter.check(request, "search", max(get_settings().auth_rate_limit * 6, 60), 60)
    wanted = [t.strip() for t in types.split(",")] if types else None
    return await unified_search(db, q, wanted, limit)


@router.get("/types")
async def search_types():
    return {"types": list(ALL_TYPES)}
