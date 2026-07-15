from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.deps import TenantContext, get_tenant_db, require_permission
from core.errors import NotFoundError
from modules.entitlements.service import resolve_entitlements
from modules.subscriptions.models import TenantSubscription
from modules.subscriptions.schemas import EntitlementsRead, SubscriptionRead

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


@router.get("/current", response_model=SubscriptionRead)
async def get_current_subscription(
    ctx: TenantContext = Depends(require_permission("subscriptions.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> SubscriptionRead:
    subscription = (
        await db.execute(
            select(TenantSubscription)
            .options(selectinload(TenantSubscription.plan))
            .where(TenantSubscription.tenant_id == ctx.tenant_id)
        )
    ).scalar_one_or_none()
    if subscription is None:
        raise NotFoundError("No subscription found for this workspace.")

    return SubscriptionRead(
        plan_key=subscription.plan.key,
        plan_name=subscription.plan.name,
        status=subscription.status,
        trial_ends_at=subscription.trial_ends_at,
        current_period_end=subscription.current_period_end,
    )


@router.get("/entitlements", response_model=EntitlementsRead)
async def get_current_entitlements(
    ctx: TenantContext = Depends(require_permission("subscriptions.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> EntitlementsRead:
    resolution = await resolve_entitlements(db, tenant_id=ctx.tenant_id)
    return EntitlementsRead(
        entitled_modules=sorted(resolution.entitled_modules),
        entitled_features=sorted(resolution.entitled_feature_keys),
        feature_limits=resolution.feature_limits,
    )
