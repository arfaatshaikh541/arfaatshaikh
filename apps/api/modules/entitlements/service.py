from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.entitlements.models import TenantFeatureOverride
from modules.subscriptions.models import (
    AddOn,
    Feature,
    Module,
    PlanFeature,
    TenantAddOn,
    TenantSubscription,
    TrialGrant,
)


@dataclass(frozen=True)
class EntitlementResolution:
    """The effective, merged entitlement set for a tenant at this instant.
    Always computed fresh from the database — never trusted from a cached
    client token (ADR: entitlements are backend-enforced and re-derived per
    request, architecture §10)."""

    entitled_modules: frozenset[str]
    entitled_feature_keys: frozenset[str]
    feature_limits: dict[str, int] = field(default_factory=dict)


async def resolve_entitlements(db: AsyncSession, *, tenant_id: uuid.UUID) -> EntitlementResolution:
    """Merges, most-specific-wins: plan features -> active add-ons ->
    active trial grants -> tenant feature overrides (grant/revoke last)."""
    now = datetime.now(UTC)

    modules_by_id: dict[uuid.UUID, str] = {
        m.id: m.key for m in (await db.execute(select(Module))).scalars().all()
    }
    features_by_id: dict[uuid.UUID, Feature] = {
        f.id: f for f in (await db.execute(select(Feature))).scalars().all()
    }

    trial_module_keys: set[str] = set()
    entitled_feature_keys: set[str] = set()
    feature_limits: dict[str, int] = {}

    def _grant_feature(feature: Feature, limit_value: int | None) -> None:
        entitled_feature_keys.add(feature.key)
        if limit_value is not None:
            feature_limits[feature.key] = limit_value

    # 1. Base plan.
    sub_result = await db.execute(
        select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_id)
    )
    subscription = sub_result.scalar_one_or_none()
    if subscription is not None and subscription.status in ("trialing", "active", "past_due"):
        plan_features = (
            await db.execute(select(PlanFeature).where(PlanFeature.plan_id == subscription.plan_id))
        ).scalars().all()
        for pf in plan_features:
            feature = features_by_id.get(pf.feature_id)
            if feature:
                _grant_feature(feature, pf.limit_value)

    # 2. Active add-ons.
    tenant_add_ons = (
        await db.execute(select(TenantAddOn).where(TenantAddOn.tenant_id == tenant_id))
    ).scalars().all()
    active_add_on_ids = {
        ao.add_on_id for ao in tenant_add_ons if ao.expires_at is None or ao.expires_at > now
    }
    if active_add_on_ids:
        add_on_rows = (
            await db.execute(select(AddOn).where(AddOn.id.in_(active_add_on_ids)))
        ).scalars().all()
        for add_on in add_on_rows:
            feature = features_by_id.get(add_on.grants_feature_id)
            if feature:
                _grant_feature(feature, None)

    # 3. Active trial grants — module-level and NOT subject to per-feature
    # overrides below (there's no feature to revoke against), so these are
    # tracked separately and unioned in at the very end.
    trial_grants = (
        await db.execute(
            select(TrialGrant).where(
                TrialGrant.tenant_id == tenant_id,
                TrialGrant.starts_at <= now,
                TrialGrant.ends_at > now,
            )
        )
    ).scalars().all()
    for grant in trial_grants:
        module_key = modules_by_id.get(grant.module_id)
        if module_key:
            trial_module_keys.add(module_key)

    # 4. Tenant-specific overrides — always the last, most-specific layer.
    overrides = (
        await db.execute(select(TenantFeatureOverride).where(TenantFeatureOverride.tenant_id == tenant_id))
    ).scalars().all()
    for override in overrides:
        if override.expires_at is not None and override.expires_at <= now:
            continue
        feature = features_by_id.get(override.feature_id)
        if feature is None:
            continue
        if override.override_type == "grant":
            _grant_feature(feature, override.limit_value)
        elif override.override_type == "revoke":
            entitled_feature_keys.discard(feature.key)

    # Module access is DERIVED from the final (post-override) feature set,
    # not accumulated independently — otherwise revoking a tenant's only
    # feature in a module would leave the module itself still entitled.
    entitled_module_keys = set(trial_module_keys)
    for feature in features_by_id.values():
        if feature.key in entitled_feature_keys:
            module_key = modules_by_id.get(feature.module_id)
            if module_key:
                entitled_module_keys.add(module_key)

    return EntitlementResolution(
        entitled_modules=frozenset(entitled_module_keys),
        entitled_feature_keys=frozenset(entitled_feature_keys),
        feature_limits=feature_limits,
    )
