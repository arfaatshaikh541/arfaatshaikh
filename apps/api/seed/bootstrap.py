"""Idempotent platform catalogue seed — permissions, roles, modules,
features, and a starter subscription plan. Safe to run in every
environment (development, staging, production); running it twice makes no
changes the second time. This is NOT fictional/demo data — see
seed/demo.py for the labelled fictional tenant used in development."""

from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.security_contracts import (
    DEFAULT_PLATFORM_ROLE_PERMISSIONS,
    DEFAULT_ROLE_PERMISSIONS,
    MODULES,
    PERMISSIONS,
    PLATFORM_ROLES,
    TENANT_ROLES,
)
from db import models_registry  # noqa: F401
from db.session import AsyncSessionLocal
from modules.permissions.models import Permission, Role, RolePermission
from modules.subscriptions.models import Feature, Module, PlanFeature, SubscriptionPlan

logger = structlog.get_logger("gridkeep.seed.bootstrap")

_PERMISSION_DESCRIPTIONS = {
    "assets.view": "View the asset inventory",
    "assets.manage": "Add, edit and remove assets",
    "integrations.view": "View connected integrations",
    "integrations.manage": "Connect, configure and revoke integrations",
    "findings.view": "View security findings",
    "findings.assign": "Assign findings to an owner",
    "findings.accept_risk": "Formally accept the risk of a finding",
    "findings.remediate": "Mark findings as remediated",
    "actions.view": "View automated actions",
    "actions.execute_safe": "Execute low-risk, reversible actions",
    "actions.approve_disruptive": "Approve moderate/high-impact actions",
    "incidents.view": "View incidents",
    "incidents.manage": "Manage incident details and tasks",
    "incidents.declare": "Declare a new incident",
    "incidents.close": "Close an incident",
    "evidence.view": "View evidence records",
    "evidence.export": "Export evidence",
    "playbooks.view": "View automation playbooks",
    "playbooks.manage": "Create and edit playbooks",
    "automations.manage": "Configure automation modes and policies",
    "compliance.view": "View compliance controls and evidence",
    "compliance.manage": "Manage compliance controls, policies and evidence",
    "reports.view": "View and generate reports",
    "trust_passport.manage": "Manage the shareable trust passport",
    "users.manage": "Invite, remove and manage workspace members",
    "roles.manage": "Manage custom roles",
    "settings.manage": "Manage workspace settings",
    "subscriptions.view": "View subscription and entitlement details",
    "platform.tenants.manage": "Manage tenants at the platform level",
    "platform.support_access": "Request just-in-time tenant support access",
    "platform.audit.view": "View platform-wide audit logs",
}

_MODULE_NAMES = {
    "asset_inventory": "Asset Inventory",
    "attack_surface": "Attack Surface Management",
    "identity_security": "Identity Security",
    "email_security": "Email Security",
    "endpoint_security": "Endpoint Security",
    "network_security": "Network Security",
    "cloud_security": "Cloud Security",
    "application_security": "Application Security",
    "data_security": "Data Security",
    "vulnerability_management": "Vulnerability Management",
    "threat_intelligence": "Threat Intelligence",
    "detection_correlation": "Detection & Correlation",
    "cyber_autopilot": "Cyber Autopilot",
    "incident_response": "Incident Response",
    "backup_resilience": "Backup & Ransomware Resilience",
    "employee_security": "Employee Security",
    "compliance": "Compliance",
    "third_party_risk": "Third-Party Risk",
    "trust_passport": "Trust Passport",
    "executive_reporting": "Executive Reporting",
    "managed_soc": "Managed SOC",
}


async def _upsert_permissions(session: AsyncSession) -> dict[str, Permission]:
    existing = {p.key: p for p in (await session.execute(select(Permission))).scalars().all()}
    for key in PERMISSIONS:
        if key not in existing:
            perm = Permission(
                key=key,
                module=key.split(".")[0],
                description=_PERMISSION_DESCRIPTIONS.get(key, key),
            )
            session.add(perm)
            existing[key] = perm
    await session.flush()
    return existing


async def _upsert_roles(
    session: AsyncSession, permissions_by_key: dict[str, Permission]
) -> None:
    existing = {
        (r.name, r.is_platform_role): r
        for r in (await session.execute(select(Role))).scalars().all()
    }

    async def _ensure_role_permissions(role: Role, keys: tuple[str, ...]) -> None:
        current = {
            rp.permission_id
            for rp in (
                await session.execute(select(RolePermission).where(RolePermission.role_id == role.id))
            ).scalars().all()
        }
        for key in keys:
            perm = permissions_by_key[key]
            if perm.id not in current:
                session.add(RolePermission(role_id=role.id, permission_id=perm.id))

    for role_name in TENANT_ROLES:
        role = existing.get((role_name, False))
        if role is None:
            role = Role(tenant_id=None, name=role_name, is_platform_role=False, is_system=True)
            session.add(role)
            await session.flush()
        await _ensure_role_permissions(role, DEFAULT_ROLE_PERMISSIONS[role_name])

    for role_name in PLATFORM_ROLES:
        role = existing.get((role_name, True))
        if role is None:
            role = Role(tenant_id=None, name=role_name, is_platform_role=True, is_system=True)
            session.add(role)
            await session.flush()
        await _ensure_role_permissions(role, DEFAULT_PLATFORM_ROLE_PERMISSIONS[role_name])

    await session.flush()


async def _upsert_modules_and_features(session: AsyncSession) -> dict[str, Feature]:
    existing_modules = {m.key: m for m in (await session.execute(select(Module))).scalars().all()}
    for key in MODULES:
        if key not in existing_modules:
            module = Module(key=key, name=_MODULE_NAMES.get(key, key))
            session.add(module)
            existing_modules[key] = module
    await session.flush()

    existing_features = {
        (f.module_id, f.key): f for f in (await session.execute(select(Feature))).scalars().all()
    }
    features_by_key: dict[str, Feature] = {}
    for key, module in existing_modules.items():
        feature_key = f"{key}.base"
        feature = existing_features.get((module.id, feature_key))
        if feature is None:
            feature = Feature(module_id=module.id, key=feature_key, name=f"{module.name} — base")
            session.add(feature)
        features_by_key[key] = feature
    await session.flush()
    return features_by_key


async def _upsert_starter_plan(session: AsyncSession, features_by_module: dict[str, Feature]) -> None:
    plan = (
        await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.key == "trial"))
    ).scalar_one_or_none()
    if plan is None:
        plan = SubscriptionPlan(key="trial", name="Free Trial", is_active=True, monthly_price_usd=None)
        session.add(plan)
        await session.flush()

    # Trial plan grants the core, non-orchestration-heavy modules that are
    # actually implemented as of Milestone 1. Later milestones extend this
    # as their modules land — this is data, adjusted by future migrations
    # or an admin tool, never a code branch.
    trial_module_keys = ("asset_inventory", "attack_surface", "executive_reporting")
    existing_plan_features = {
        pf.feature_id
        for pf in (
            await session.execute(select(PlanFeature).where(PlanFeature.plan_id == plan.id))
        ).scalars().all()
    }
    for module_key in trial_module_keys:
        feature = features_by_module[module_key]
        if feature.id not in existing_plan_features:
            session.add(PlanFeature(plan_id=plan.id, feature_id=feature.id, limit_value=None))
    await session.flush()


async def run_bootstrap() -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            permissions_by_key = await _upsert_permissions(session)
            await _upsert_roles(session, permissions_by_key)
            features_by_module = await _upsert_modules_and_features(session)
            await _upsert_starter_plan(session, features_by_module)
    logger.info("bootstrap_seed_complete")


if __name__ == "__main__":
    asyncio.run(run_bootstrap())
