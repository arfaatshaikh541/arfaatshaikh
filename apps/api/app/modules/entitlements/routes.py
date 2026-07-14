from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.db import get_db
from app.dependencies.tenant import get_tenant_context
from app.modules.entitlements import service as entitlements_service

router = APIRouter(prefix="/me", tags=["entitlements"])


@router.get("/entitlements")
def get_my_entitlements(ctx: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> dict:
    """The single source of truth the frontend polls after login/tenant
    switch to decide what to render. Backend routes independently
    re-check entitlements — this endpoint exists purely for UI hinting."""
    entitlements = entitlements_service.resolve_entitlements(db, ctx.tenant_id)
    return {
        "tenant_id": str(ctx.tenant_id),
        "plan_code": entitlements.plan_code,
        "subscription_status": entitlements.subscription_status,
        "modules": entitlements.modules,
        "features": entitlements.features,
        "role_name": ctx.role_name,
        "permissions": sorted(ctx.permission_codes),
        "tenant_status": ctx.tenant_status.value,
    }
