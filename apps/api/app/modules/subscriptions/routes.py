from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.db import get_db
from app.dependencies.permissions import require_permission
from app.modules.entitlements import service as entitlements_service
from app.modules.subscriptions import service as subscriptions_service

router = APIRouter(prefix="/tenant/subscription", tags=["tenant-subscription"])


@router.get("")
def get_subscription(ctx: TenantContext = Depends(require_permission("subscriptions.view")), db: Session = Depends(get_db)) -> dict:
    subscription = subscriptions_service.get_tenant_subscription(db, ctx.tenant_id)
    entitlements = entitlements_service.resolve_entitlements(db, ctx.tenant_id)
    return {
        "plan_code": entitlements.plan_code,
        "status": subscription.status.value if subscription else None,
        "current_period_end": subscription.current_period_end.isoformat() if subscription and subscription.current_period_end else None,
        "trial_ends_at": subscription.trial_ends_at.isoformat() if subscription and subscription.trial_ends_at else None,
        "modules": entitlements.modules,
        "features": entitlements.features,
    }
