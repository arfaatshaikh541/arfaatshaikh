import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.subscriptions.models import (
    AddOn,
    Feature,
    FeatureOverride,
    PlanFeature,
    SubscriptionPlan,
    TenantAddOn,
    TenantSubscription,
)


async def get_plan_by_key(session: AsyncSession, key: str) -> SubscriptionPlan | None:
    stmt = select(SubscriptionPlan).where(SubscriptionPlan.key == key)
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_active_plans(session: AsyncSession) -> list[SubscriptionPlan]:
    stmt = (
        select(SubscriptionPlan)
        .where(SubscriptionPlan.is_active.is_(True))
        .order_by(SubscriptionPlan.monthly_price_usd)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_plan_by_stripe_price_id(
    session: AsyncSession, stripe_price_id: str
) -> SubscriptionPlan | None:
    stmt = select(SubscriptionPlan).where(SubscriptionPlan.stripe_price_id == stripe_price_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_tenant_subscription(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    plan_id: uuid.UUID,
    current_period_start,
    current_period_end,
    status: str = "active",
) -> TenantSubscription:
    sub = TenantSubscription(
        tenant_id=tenant_id,
        plan_id=plan_id,
        status=status,
        current_period_start=current_period_start,
        current_period_end=current_period_end,
    )
    session.add(sub)
    await session.flush()
    return sub


async def get_active_subscription(
    session: AsyncSession, tenant_id: uuid.UUID
) -> TenantSubscription | None:
    stmt = select(TenantSubscription).where(
        TenantSubscription.tenant_id == tenant_id, TenantSubscription.status == "active"
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_subscription_for_tenant(
    session: AsyncSession, tenant_id: uuid.UUID
) -> TenantSubscription | None:
    """Unlike `get_active_subscription`, returns the tenant's subscription
    row regardless of its current `status` - needed by the billing webhook
    handler, which must find and update the existing row even when Stripe
    is reporting it's no longer active."""
    stmt = select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def update_tenant_subscription_plan(
    session: AsyncSession,
    subscription: TenantSubscription,
    *,
    plan_id: uuid.UUID,
    status: str,
    current_period_start,
    current_period_end,
) -> TenantSubscription:
    """Mutates the tenant's single subscription row in place - there is
    exactly one `TenantSubscription` per tenant (seeded once at tenant
    creation; see `app.seed.seed_data`/`app.modules.tenancy.services`),
    the same "current-state columns mutated in place, a separate table is
    the audit trail" pattern `Export`/`CampaignJob` already use. Here,
    `BillingEvent` is that audit trail."""
    subscription.plan_id = plan_id
    subscription.status = status
    subscription.current_period_start = current_period_start
    subscription.current_period_end = current_period_end
    await session.flush()
    return subscription


async def get_plan_features(session: AsyncSession, plan_id: uuid.UUID) -> dict[str, dict]:
    stmt = (
        select(Feature.key, PlanFeature.value)
        .join(PlanFeature, PlanFeature.feature_id == Feature.id)
        .where(PlanFeature.plan_id == plan_id)
    )
    result = await session.execute(stmt)
    return {row[0]: row[1] for row in result.all()}


async def get_active_tenant_add_ons(session: AsyncSession, tenant_id: uuid.UUID) -> dict[str, dict]:
    stmt = (
        select(Feature.key, AddOn.value)
        .join(AddOn, AddOn.feature_id == Feature.id)
        .join(TenantAddOn, TenantAddOn.add_on_id == AddOn.id)
        .where(TenantAddOn.tenant_id == tenant_id, TenantAddOn.status == "active")
    )
    result = await session.execute(stmt)
    return {row[0]: row[1] for row in result.all()}


async def get_active_feature_overrides(
    session: AsyncSession, tenant_id: uuid.UUID
) -> dict[str, dict]:
    now = datetime.now(UTC)
    stmt = (
        select(Feature.key, FeatureOverride.value)
        .join(FeatureOverride, FeatureOverride.feature_id == Feature.id)
        .where(
            FeatureOverride.tenant_id == tenant_id,
            (FeatureOverride.expires_at.is_(None)) | (FeatureOverride.expires_at > now),
        )
    )
    result = await session.execute(stmt)
    return {row[0]: row[1] for row in result.all()}
