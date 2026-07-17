"""Fictional seed data for local development and demos.

Everything created here is clearly fictional:
  - Platform: "GRIDKEEP Platform Demo"
  - Tenant:   "Northstar Digital Solutions Demo"
  - Users:    5 demo accounts covering the default tenant roles, plus one
              platform-staff demo account.

This script is idempotent: re-running it does not create duplicate rows -
it looks up existing rows by their natural key (email, plan key, role
name, permission key) before inserting.

Run with: uv run python -m app.seed.seed_data
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.db import AsyncSessionLocal, set_platform_bypass, set_tenant_context
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.modules.identity.models import User
from app.modules.permissions import repositories as perm_repo
from app.modules.permissions.catalog import PERMISSIONS, PLATFORM_ROLE_DEFAULTS
from app.modules.permissions.models import Permission, PlatformRoleAssignment
from app.modules.subscriptions import repositories as sub_repo
from app.modules.subscriptions.models import Feature, PlanFeature, SubscriptionPlan
from app.modules.tenancy import repositories as tenancy_repo
from app.modules.tenancy.services import (
    seed_default_roles_and_permissions,
)  # reuse tenant-role seeding
from app.modules.usage import repositories as usage_repo
from app.modules.usage.services import ensure_wallet, grant_credits

logger = get_logger("gridkeep.seed")

DEMO_PASSWORD = "GridkeepDemo!2026"

DEMO_TENANT_NAME = "Northstar Digital Solutions Demo"

DEMO_TENANT_USERS = [
    ("owner@northstar-demo.gridkeep.local", "Nadia Owner (Demo)", "Owner"),
    ("campaigns@northstar-demo.gridkeep.local", "Cameron Campaigns (Demo)", "Campaign Manager"),
    ("sales-manager@northstar-demo.gridkeep.local", "Sam Sales-Manager (Demo)", "Sales Manager"),
    ("sales-rep@northstar-demo.gridkeep.local", "Riley Sales-Rep (Demo)", "Sales Representative"),
    ("viewer@northstar-demo.gridkeep.local", "Vic Viewer (Demo)", "Read-Only Viewer"),
]

PLATFORM_DEMO_USER = ("platform-admin@gridkeep-platform-demo.local", "Piper Platform-Admin (Demo)")

SUBSCRIPTION_PLANS = [
    # key, name, description, monthly_price_usd, monthly_credit_grant, max_team_members
    ("trial", "Trial", "14-day trial plan (GRIDKEEP Platform Demo)", 0, 250, 3),
    ("starter", "Starter", "Entry commercial plan", 199, 1000, 10),
    ("growth", "Growth", "Growth commercial plan", 599, 5000, 25),
    ("scale", "Scale", "Scale commercial plan", 1499, 20000, 100),
]


async def seed_permissions(session) -> dict[str, Permission]:
    existing = {p.key: p for p in await perm_repo.get_all_permissions(session)}
    for key, description, category in PERMISSIONS:
        if key not in existing:
            perm = Permission(key=key, description=description, category=category)
            session.add(perm)
            await session.flush()
            existing[key] = perm
    return existing


async def seed_platform_roles(
    session, permissions_by_key: dict[str, Permission]
) -> dict[str, uuid.UUID]:
    await set_platform_bypass(session)
    role_ids: dict[str, uuid.UUID] = {}
    for role_name, permission_keys in PLATFORM_ROLE_DEFAULTS.items():
        existing_role = await perm_repo.get_role_by_tenant_and_name(
            session, tenant_id=None, name=role_name
        )
        if existing_role is None:
            role = await perm_repo.create_role(
                session,
                tenant_id=None,
                name=role_name,
                description=f"{role_name} (platform role)",
                is_platform_role=True,
            )
            grant_ids = [
                permissions_by_key[k].id for k in permission_keys if k in permissions_by_key
            ]
            await perm_repo.grant_permissions_to_role(
                session, role_id=role.id, tenant_id=None, permission_ids=grant_ids
            )
            role_ids[role_name] = role.id
        else:
            role_ids[role_name] = existing_role.id
    return role_ids


async def seed_subscription_plans(session) -> dict[str, SubscriptionPlan]:
    max_team_members_feature = (
        await session.execute(select(Feature).where(Feature.key == "max_team_members"))
    ).scalar_one_or_none()
    if max_team_members_feature is None:
        max_team_members_feature = Feature(
            key="max_team_members",
            name="Maximum team members",
            description="Cap on active tenant memberships",
            value_type="limit",
        )
        session.add(max_team_members_feature)
        await session.flush()

    plans: dict[str, SubscriptionPlan] = {}
    for key, name, description, price, credit_grant, max_members in SUBSCRIPTION_PLANS:
        plan = (
            await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.key == key))
        ).scalar_one_or_none()
        if plan is None:
            plan = SubscriptionPlan(
                key=key,
                name=name,
                description=description,
                monthly_price_usd=price,
                monthly_credit_grant=credit_grant,
            )
            session.add(plan)
            await session.flush()

            session.add(
                PlanFeature(
                    plan_id=plan.id,
                    feature_id=max_team_members_feature.id,
                    value={"limit": max_members},
                )
            )
            await session.flush()
        plans[key] = plan
    return plans


async def get_or_create_demo_platform_user(session) -> User:
    email, full_name = PLATFORM_DEMO_USER
    stmt = select(User).where(User.email == email)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(DEMO_PASSWORD),
            full_name=full_name,
            email_verified=True,
            is_platform_user=True,
        )
        session.add(user)
        await session.flush()
    return user


async def ensure_platform_role_assignment(session, user: User, role_id: uuid.UUID) -> None:
    stmt = select(PlatformRoleAssignment).where(
        PlatformRoleAssignment.user_id == user.id, PlatformRoleAssignment.role_id == role_id
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is None:
        session.add(PlatformRoleAssignment(user_id=user.id, role_id=role_id))
        await session.flush()


async def get_or_create_demo_tenant(session):
    existing = await tenancy_repo.get_tenant_by_slug(session, "northstar-digital-solutions-demo")
    if existing is not None:
        return existing, False

    tenant = await tenancy_repo.create_tenant(
        session, name=DEMO_TENANT_NAME, slug="northstar-digital-solutions-demo", status="active"
    )
    await set_tenant_context(session, tenant.id)
    await tenancy_repo.create_tenant_settings(session, tenant_id=tenant.id)
    return tenant, True


async def seed_demo_tenant_users_and_memberships(
    session, tenant, role_ids_by_name: dict[str, uuid.UUID]
) -> None:
    await set_tenant_context(session, tenant.id)
    for email, full_name, role_name in DEMO_TENANT_USERS:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password(DEMO_PASSWORD),
                full_name=full_name,
                email_verified=True,
            )
            session.add(user)
            await session.flush()

        existing_membership = await tenancy_repo.get_membership(
            session, tenant_id=tenant.id, user_id=user.id
        )
        if existing_membership is None:
            await tenancy_repo.create_membership(
                session, tenant_id=tenant.id, user_id=user.id, role_id=role_ids_by_name[role_name]
            )


async def seed() -> None:
    configure_logging()
    async with AsyncSessionLocal() as session:
        permissions_by_key = await seed_permissions(session)
        await seed_platform_roles(session, permissions_by_key)
        await seed_subscription_plans(session)

        platform_user = await get_or_create_demo_platform_user(session)
        super_admin_role = await perm_repo.get_role_by_tenant_and_name(
            session, tenant_id=None, name="Platform Super Admin"
        )
        if super_admin_role is not None:
            await ensure_platform_role_assignment(session, platform_user, super_admin_role.id)

        tenant, created = await get_or_create_demo_tenant(session)
        if created:
            role_ids_by_name = await seed_default_roles_and_permissions(session, tenant.id)
        else:
            await set_tenant_context(session, tenant.id)
            roles = await perm_repo.list_roles_for_tenant(session, tenant.id)
            role_ids_by_name = {r.name: r.id for r in roles}

        await seed_demo_tenant_users_and_memberships(session, tenant, role_ids_by_name)

        await ensure_wallet(session, tenant.id)
        trial_plan = (
            await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.key == "trial"))
        ).scalar_one_or_none()
        if trial_plan is not None:
            active_sub = await sub_repo.get_active_subscription(session, tenant.id)
            if active_sub is None:
                now = datetime.now(UTC)
                await sub_repo.create_tenant_subscription(
                    session,
                    tenant_id=tenant.id,
                    plan_id=trial_plan.id,
                    current_period_start=now,
                    current_period_end=now + timedelta(days=14),
                )

        existing_grants = await usage_repo.list_transactions_for_tenant(session, tenant.id)
        if not existing_grants:
            await grant_credits(
                session,
                tenant_id=tenant.id,
                amount=1000,
                type_="grant_recurring",
                reference="seed:demo_grant",
            )

        await session.commit()
        logger.info(
            "seed_complete",
            tenant_slug=tenant.slug,
            demo_password_hint="see docs/project-status.md",
        )


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
