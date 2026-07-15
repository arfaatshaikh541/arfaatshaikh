import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from db.session import set_tenant_context
from modules.entitlements.models import TenantFeatureOverride
from modules.entitlements.service import resolve_entitlements
from modules.subscriptions.models import Feature, Module, SubscriptionPlan, TenantSubscription
from modules.tenancy.models import Tenant, TenantSecurityProfile, TenantSettings

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _make_tenant(session, name: str) -> uuid.UUID:
    tenant_id = uuid.uuid4()
    slug = f"{name.lower().replace(' ', '-')}-{tenant_id.hex[:6]}"
    session.add(Tenant(id=tenant_id, name=name, slug=slug, status="active"))
    await session.flush()
    await set_tenant_context(session, tenant_id)
    session.add(TenantSettings(tenant_id=tenant_id, display_name=name))
    session.add(TenantSecurityProfile(tenant_id=tenant_id))
    await session.flush()
    return tenant_id


async def test_no_subscription_means_no_entitlements(db):
    tenant_id = await _make_tenant(db, "No Sub Co")
    await db.commit()
    await set_tenant_context(db, tenant_id)

    resolution = await resolve_entitlements(db, tenant_id=tenant_id)
    assert resolution.entitled_modules == frozenset()


async def test_trial_plan_grants_expected_modules(db):
    tenant_id = await _make_tenant(db, "Trial Co")
    plan = (await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.key == "trial"))).scalar_one()
    db.add(TenantSubscription(tenant_id=tenant_id, plan_id=plan.id, status="active"))
    await db.commit()
    await set_tenant_context(db, tenant_id)

    resolution = await resolve_entitlements(db, tenant_id=tenant_id)
    assert "asset_inventory" in resolution.entitled_modules
    assert "attack_surface" in resolution.entitled_modules
    assert "compliance" not in resolution.entitled_modules  # not on the trial plan


async def test_expired_subscription_grants_nothing(db):
    tenant_id = await _make_tenant(db, "Expired Co")
    plan = (await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.key == "trial"))).scalar_one()
    db.add(TenantSubscription(tenant_id=tenant_id, plan_id=plan.id, status="canceled"))
    await db.commit()
    await set_tenant_context(db, tenant_id)

    resolution = await resolve_entitlements(db, tenant_id=tenant_id)
    assert resolution.entitled_modules == frozenset()


async def test_tenant_override_can_grant_extra_feature(db):
    tenant_id = await _make_tenant(db, "Override Co")

    compliance_module = (
        await db.execute(select(Module).where(Module.key == "compliance"))
    ).scalar_one()
    compliance_feature = (
        await db.execute(select(Feature).where(Feature.module_id == compliance_module.id))
    ).scalar_one()

    db.add(
        TenantFeatureOverride(
            tenant_id=tenant_id,
            feature_id=compliance_feature.id,
            override_type="grant",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    resolution = await resolve_entitlements(db, tenant_id=tenant_id)
    assert "compliance" in resolution.entitled_modules


async def test_expired_override_does_not_grant(db):
    tenant_id = await _make_tenant(db, "ExpiredOverride Co")

    compliance_module = (
        await db.execute(select(Module).where(Module.key == "compliance"))
    ).scalar_one()
    compliance_feature = (
        await db.execute(select(Feature).where(Feature.module_id == compliance_module.id))
    ).scalar_one()

    db.add(
        TenantFeatureOverride(
            tenant_id=tenant_id,
            feature_id=compliance_feature.id,
            override_type="grant",
            expires_at=datetime.now(UTC) - timedelta(days=1),  # already expired
        )
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    resolution = await resolve_entitlements(db, tenant_id=tenant_id)
    assert "compliance" not in resolution.entitled_modules


async def test_override_revoke_removes_plan_granted_feature(db):
    tenant_id = await _make_tenant(db, "Revoke Co")
    plan = (await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.key == "trial"))).scalar_one()
    db.add(TenantSubscription(tenant_id=tenant_id, plan_id=plan.id, status="active"))

    asset_module = (
        await db.execute(select(Module).where(Module.key == "asset_inventory"))
    ).scalar_one()
    asset_feature = (
        await db.execute(select(Feature).where(Feature.module_id == asset_module.id))
    ).scalar_one()
    db.add(
        TenantFeatureOverride(tenant_id=tenant_id, feature_id=asset_feature.id, override_type="revoke")
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    resolution = await resolve_entitlements(db, tenant_id=tenant_id)
    assert "asset_inventory" not in resolution.entitled_modules
    assert "attack_surface" in resolution.entitled_modules  # untouched by the revoke
