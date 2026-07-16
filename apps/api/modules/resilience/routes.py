from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import TenantContext, get_tenant_db, require_permission
from modules.resilience import service as resilience_service
from modules.resilience.schemas import ResilienceSummaryRead

router = APIRouter(prefix="/api/resilience", tags=["resilience"])


@router.get("/summary", response_model=ResilienceSummaryRead)
async def get_resilience_summary(
    ctx: TenantContext = Depends(require_permission("assets.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> ResilienceSummaryRead:
    summary = await resilience_service.get_resilience_summary(db, tenant_id=ctx.tenant_id)
    return ResilienceSummaryRead(**summary)
