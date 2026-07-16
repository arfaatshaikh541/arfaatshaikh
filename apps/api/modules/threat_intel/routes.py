from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import TenantContext, get_tenant_db, require_permission
from modules.threat_intel import service as threat_intel_service
from modules.threat_intel.schemas import IndicatorRead, MatchedAssetRead

router = APIRouter(prefix="/api/threat-intel", tags=["threat-intel"])


@router.get("/indicators", response_model=list[IndicatorRead])
async def list_indicators(
    ctx: TenantContext = Depends(require_permission("findings.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[IndicatorRead]:
    indicators = await threat_intel_service.list_indicators(db, tenant_id=ctx.tenant_id)
    return [
        IndicatorRead(
            **{k: v for k, v in indicator.items() if k != "matches"},
            matches=[MatchedAssetRead(**m) for m in indicator["matches"]],
        )
        for indicator in indicators
    ]
