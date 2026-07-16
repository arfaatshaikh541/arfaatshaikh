from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import TenantContext, get_tenant_db, require_permission
from modules.reporting import service as reporting_service
from modules.reporting.schemas import ExecutiveSummaryRead

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/executive-summary", response_model=ExecutiveSummaryRead)
async def get_executive_summary(
    ctx: TenantContext = Depends(require_permission("reports.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> ExecutiveSummaryRead:
    summary = await reporting_service.get_executive_summary(db, tenant_id=ctx.tenant_id)
    return ExecutiveSummaryRead(**summary)
