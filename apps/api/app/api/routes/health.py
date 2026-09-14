from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.infrastructure.health import check_dependencies

router = APIRouter(prefix="/health", tags=["health"])


class LivenessResponse(BaseModel):
    status: Literal["ok"]
    service: str = "world-of-islam-api"


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str = "world-of-islam-api"
    dependencies: dict[str, bool]


@router.get("/live", response_model=LivenessResponse)
async def live() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
async def ready(response: Response) -> ReadinessResponse:
    health = await check_dependencies()
    if not health.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="degraded", dependencies=health.as_dict())
    return ReadinessResponse(status="ok", dependencies=health.as_dict())
