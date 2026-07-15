"""FICTIONAL demo data for local development and product demonstrations.

Creates:
  - one platform user ("GRIDKEEP Platform Demo") with the platform_super_admin role
  - one demo tenant ("Northstar Advisory Demo") on the trial plan
  - five fictional users, one per default tenant role

None of this data represents a real organisation, person, or credential.
Do NOT run this seed against a production database — `run_demo_seed`
refuses to run when `settings.is_production` is true.
"""

from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select

from core.config import settings
from core.security import hash_password
from db import models_registry  # noqa: F401
from db.session import AsyncSessionLocal, set_tenant_context
from modules.identity.models import User
from modules.permissions.models import Membership, Role
from modules.subscriptions.models import SubscriptionPlan, TenantSubscription
from modules.tenancy.models import Tenant, TenantSecurityProfile, TenantSettings

logger = structlog.get_logger("gridkeep.seed.demo")

DEMO_PASSWORD = "Gridkeep-Demo-2026!"  # fictional, local-dev-only credential

DEMO_TENANT_SLUG = "northstar-advisory-demo"
DEMO_TENANT_NAME = "Northstar Advisory Demo"
DEMO_EMAIL_DOMAIN = "northstar-advisory-demo.gridkeep.example"

DEMO_TENANT_USERS = [
    ("tenant_owner", "Amara Osei", f"amara.owner@{DEMO_EMAIL_DOMAIN}"),
    ("security_administrator", "Farid Haddad", f"farid.secadmin@{DEMO_EMAIL_DOMAIN}"),
    ("it_administrator", "Priya Nair", f"priya.itadmin@{DEMO_EMAIL_DOMAIN}"),
    ("security_analyst", "Daniyar Suleimenov", f"daniyar.analyst@{DEMO_EMAIL_DOMAIN}"),
    ("executive_viewer", "Layla Marzouq", f"layla.exec@{DEMO_EMAIL_DOMAIN}"),
]

PLATFORM_DEMO_EMAIL = "platform.admin@gridkeep-platform.example"
PLATFORM_DEMO_NAME = "GRIDKEEP Platform Demo Admin"


async def run_demo_seed() -> None:
    if settings.is_production:
        raise RuntimeError("Refusing to run fictional demo seed against a production environment.")

    async with AsyncSessionLocal() as session:
        async with session.begin():
            # --- platform demo user ---
            platform_role = (
                await session.execute(
                    select(Role).where(Role.name == "platform_super_admin", Role.is_platform_role.is_(True))
                )
            ).scalar_one()

            platform_user = (
                await session.execute(select(User).where(User.email == PLATFORM_DEMO_EMAIL))
            ).scalar_one_or_none()
            if platform_user is None:
                platform_user = User(
                    email=PLATFORM_DEMO_EMAIL,
                    password_hash=hash_password(DEMO_PASSWORD),
                    full_name=PLATFORM_DEMO_NAME,
                    email_verified=True,
                    is_platform_user=True,
                    platform_role_id=platform_role.id,
                )
                session.add(platform_user)
                await session.flush()

            # --- demo tenant ---
            tenant = (
                await session.execute(select(Tenant).where(Tenant.slug == DEMO_TENANT_SLUG))
            ).scalar_one_or_none()
            if tenant is None:
                tenant = Tenant(
                    name=DEMO_TENANT_NAME,
                    slug=DEMO_TENANT_SLUG,
                    status="active",
                    industry="Professional services (fictional)",
                    country_code="AE",
                    is_demo=True,
                )
                session.add(tenant)
                await session.flush()

            await set_tenant_context(session, tenant.id)

            if (
                await session.execute(
                    select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
                )
            ).scalar_one_or_none() is None:
                session.add(TenantSettings(tenant_id=tenant.id, display_name=DEMO_TENANT_NAME))

            if (
                await session.execute(
                    select(TenantSecurityProfile).where(TenantSecurityProfile.tenant_id == tenant.id)
                )
            ).scalar_one_or_none() is None:
                session.add(TenantSecurityProfile(tenant_id=tenant.id))

            trial_plan = (
                await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.key == "trial"))
            ).scalar_one()
            if (
                await session.execute(
                    select(TenantSubscription).where(TenantSubscription.tenant_id == tenant.id)
                )
            ).scalar_one_or_none() is None:
                session.add(
                    TenantSubscription(tenant_id=tenant.id, plan_id=trial_plan.id, status="active")
                )

            for role_name, full_name, email in DEMO_TENANT_USERS:
                role = (
                    await session.execute(
                        select(Role).where(Role.name == role_name, Role.is_platform_role.is_(False))
                    )
                ).scalar_one()

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

                existing_membership = (
                    await session.execute(
                        select(Membership).where(
                            Membership.tenant_id == tenant.id, Membership.user_id == user.id
                        )
                    )
                ).scalar_one_or_none()
                if existing_membership is None:
                    session.add(
                        Membership(
                            tenant_id=tenant.id, user_id=user.id, role_id=role.id, status="active"
                        )
                    )

    logger.info(
        "demo_seed_complete",
        tenant_slug=DEMO_TENANT_SLUG,
        demo_password=DEMO_PASSWORD,
        note="Fictional data — do not use in production.",
    )


if __name__ == "__main__":
    asyncio.run(run_demo_seed())
