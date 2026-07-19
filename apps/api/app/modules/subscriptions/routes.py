from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.exceptions import ResourceNotFoundError
from app.dependencies import TenantContext, require_permission
from app.modules.entitlements.service import resolve_entitlements
from app.modules.subscriptions import repositories as repo
from app.modules.subscriptions.models import SubscriptionPlan
from app.modules.subscriptions.schemas import PlanListResponse, PlanResponse, SubscriptionResponse

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans", response_model=PlanListResponse)
async def list_plans(
    _ctx: TenantContext = Depends(require_permission("billing.view")),
    db: AsyncSession = Depends(get_db),
):
    plans = await repo.list_active_plans(db)
    return PlanListResponse(
        plans=[
            PlanResponse(
                key=p.key,
                name=p.name,
                description=p.description,
                monthly_price_usd=float(p.monthly_price_usd),
                monthly_credit_grant=p.monthly_credit_grant,
                checkout_available=bool(p.stripe_price_id),
            )
            for p in plans
        ]
    )


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    ctx: TenantContext = Depends(require_permission("billing.view")),
    db: AsyncSession = Depends(get_db),
):
    subscription = await repo.get_active_subscription(db, ctx.tenant_id)
    if subscription is None:
        raise ResourceNotFoundError("This tenant has no active subscription.")
    plan = (
        await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.plan_id)
        )
    ).scalar_one()
    entitlements = await resolve_entitlements(db, ctx.tenant_id)

    return SubscriptionResponse(
        tenant_id=ctx.tenant_id,
        plan_key=plan.key,
        plan_name=plan.name,
        status=subscription.status,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        entitlements=entitlements,
    )
