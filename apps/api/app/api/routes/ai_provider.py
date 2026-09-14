from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.dependencies.auth import get_current_user
from app.core.config import get_settings
from app.core.rate_limit import rate_limiter
from app.models.identity import User
from app.schemas.ai_provider import AIGenerateRequest, AIGenerateResponse, AIStatusResponse
from app.services.ai_provider import get_ai_provider

router = APIRouter(prefix="/intelligence", tags=["intelligence"])
settings = get_settings()


@router.get("/status", response_model=AIStatusResponse)
async def status(_: Annotated[User, Depends(get_current_user)]) -> AIStatusResponse:
    provider = get_ai_provider(settings)
    return AIStatusResponse(
        mode=settings.ai_mode,
        provider=provider.name,
        available=await provider.is_available(),
        external_ai_enabled=settings.external_ai_enabled,
    )


@router.post("/generate", response_model=AIGenerateResponse)
async def generate(
    payload: AIGenerateRequest,
    request: Request,
    _: Annotated[User, Depends(get_current_user)],
) -> AIGenerateResponse:
    await rate_limiter.check(request, "ai-generate", 20, 60)
    provider = get_ai_provider(settings)
    result = await provider.generate(payload.prompt)
    return AIGenerateResponse(
        available=result.available, provider=result.provider, text=result.text, error=result.error,
    )
