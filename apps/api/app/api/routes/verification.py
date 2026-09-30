from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api.dependencies.auth import DbSession
from app.core.config import get_settings
from app.core.rate_limit import rate_limiter
from app.services.verification import verify_text

router = APIRouter(prefix="/verification", tags=["verification"])


class VerifyTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("/text")
async def verify(payload: VerifyTextRequest, request: Request, db: DbSession):
    await rate_limiter.check(request, "verify", max(get_settings().auth_rate_limit * 6, 60), 60)
    return await verify_text(db, payload.text)
