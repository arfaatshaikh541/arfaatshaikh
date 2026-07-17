"""EntitlementResolver: computes a tenant's effective entitlement set as
plan features + add-ons + feature overrides.

This is a read path only in Milestone 1 - the write paths that grant plan
features, add-ons and overrides live in `subscriptions`/`platform_admin`.
Every entitlement-gated action re-checks this resolver at request time;
there is no time-based cache in Milestone 1 (correctness over
micro-optimization until a real performance need is measured), but the
function boundary here is exactly where a future Redis cache with
explicit invalidation-on-write would be layered in.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntitlementDeniedError
from app.modules.subscriptions import repositories as sub_repo


async def resolve_entitlements(session: AsyncSession, tenant_id: uuid.UUID) -> dict[str, dict]:
    subscription = await sub_repo.get_active_subscription(session, tenant_id)
    entitlements: dict[str, dict] = {}

    if subscription is not None:
        entitlements.update(await sub_repo.get_plan_features(session, subscription.plan_id))

    add_on_features = await sub_repo.get_active_tenant_add_ons(session, tenant_id)
    for key, value in add_on_features.items():
        entitlements[key] = value

    overrides = await sub_repo.get_active_feature_overrides(session, tenant_id)
    for key, value in overrides.items():
        entitlements[key] = value

    return entitlements


async def require_entitlement(
    session: AsyncSession, tenant_id: uuid.UUID, feature_key: str
) -> dict:
    entitlements = await resolve_entitlements(session, tenant_id)
    value = entitlements.get(feature_key)
    if value is None:
        raise EntitlementDeniedError(f"Your plan does not include: {feature_key}")
    if isinstance(value, dict) and value.get("enabled") is False:
        raise EntitlementDeniedError(f"Your plan does not include: {feature_key}")
    return value


async def check_limit(
    session: AsyncSession, tenant_id: uuid.UUID, feature_key: str, current_count: int
) -> None:
    """Raises EntitlementDeniedError if current_count would meet/exceed the
    plan's configured limit for feature_key (value shape: {"limit": N})."""
    entitlements = await resolve_entitlements(session, tenant_id)
    value = entitlements.get(feature_key)
    if value is None:
        raise EntitlementDeniedError(f"Your plan does not include: {feature_key}")
    limit = value.get("limit") if isinstance(value, dict) else None
    if limit is not None and current_count >= limit:
        raise EntitlementDeniedError(f"Plan limit reached for {feature_key} ({limit}).")
