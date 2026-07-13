"""Idempotent local/demo seed data.

Run with: python -m app.seed

Creates:
- A platform super admin account.
- A demo tenant, "Rafana Advisory Demo", with Owner / Manager / Sales Agent
  users and the default role set.
- A demo subscription plan + active subscription for that tenant.

All demo data is fictional and clearly labeled with a "[DEMO]" prefix in
display names, per the product requirement that demo data never look like
real customer data. Safe to run multiple times - it checks for existing
rows before creating anything.
"""

from __future__ import annotations

from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.subscription import Subscription, SubscriptionPlan
from app.repositories.membership import MembershipRepository
from app.repositories.role import RoleRepository
from app.repositories.tenant import TenantRepository
from app.repositories.user import UserRepository

logger = get_logger("app.seed")

PLATFORM_SUPER_ADMIN_EMAIL = "superadmin@leadflow-demo.io"
PLATFORM_SUPER_ADMIN_PASSWORD = "SuperAdmin!2026"

DEMO_TENANT_SLUG = "rafana-advisory-demo"
DEMO_TENANT_NAME = "[DEMO] Rafana Advisory"

DEMO_USERS = [
    {
        "email": "owner@rafana-demo.leadflow-demo.io",
        "password": "DemoOwner!2026",
        "first_name": "[DEMO]",
        "last_name": "Tenant Owner",
        "role_slug": "owner",
    },
    {
        "email": "manager@rafana-demo.leadflow-demo.io",
        "password": "DemoManager!2026",
        "first_name": "[DEMO]",
        "last_name": "Manager",
        "role_slug": "manager",
    },
    {
        "email": "sales@rafana-demo.leadflow-demo.io",
        "password": "DemoSales!2026",
        "first_name": "[DEMO]",
        "last_name": "Sales Agent",
        "role_slug": "sales_agent",
    },
]


def seed() -> None:
    db = SessionLocal()
    try:
        users = UserRepository(db)
        tenants = TenantRepository(db)
        roles = RoleRepository(db)
        memberships = MembershipRepository(db)

        roles.sync_permission_catalog()

        super_admin = users.get_by_email(PLATFORM_SUPER_ADMIN_EMAIL)
        if super_admin is None:
            super_admin = users.create(
                email=PLATFORM_SUPER_ADMIN_EMAIL,
                hashed_password=hash_password(PLATFORM_SUPER_ADMIN_PASSWORD),
                first_name="Platform",
                last_name="Super Admin",
                is_platform_super_admin=True,
                email_verified=True,
            )
            logger.info(
                "seed.super_admin_created", extra={"extra_fields": {"email": super_admin.email}}
            )
        else:
            logger.info("seed.super_admin_exists")

        tenant = tenants.get_by_slug(DEMO_TENANT_SLUG)
        if tenant is None:
            tenant = tenants.create(
                slug=DEMO_TENANT_SLUG,
                name=DEMO_TENANT_NAME,
                legal_name="[DEMO] Rafana Advisory Professional Services LLC",
                timezone="Asia/Dubai",
                currency="AED",
            )
            settings = tenants.get_settings(tenant.id)
            if settings is not None:
                settings.contact_email = "hello@rafana-demo.leadflow-demo.io"
                settings.privacy_text = (
                    "[DEMO DATA] This is fictional demo content for the Rafana Advisory "
                    "Demo tenant and does not represent a real business."
                )
            role_map = roles.create_defaults_for_tenant(tenant.id)
            logger.info("seed.tenant_created", extra={"extra_fields": {"slug": tenant.slug}})
        else:
            role_map = {r.slug: r for r in roles.list_for_tenant(tenant.id)}
            logger.info("seed.tenant_exists")

        for demo_user in DEMO_USERS:
            user = users.get_by_email(demo_user["email"])
            if user is None:
                user = users.create(
                    email=demo_user["email"],
                    hashed_password=hash_password(demo_user["password"]),
                    first_name=demo_user["first_name"],
                    last_name=demo_user["last_name"],
                    email_verified=True,
                )
            existing_membership = memberships.get_for_user_and_tenant(user.id, tenant.id)
            if existing_membership is None:
                role = role_map[demo_user["role_slug"]]
                memberships.create(tenant_id=tenant.id, user_id=user.id, role_id=role.id)
                logger.info(
                    "seed.member_created",
                    extra={"extra_fields": {"email": user.email, "role": demo_user["role_slug"]}},
                )

        plan = db.query(SubscriptionPlan).filter_by(code="growth").one_or_none()
        if plan is None:
            plan = SubscriptionPlan(
                code="growth",
                name="Growth",
                price_cents=99900,
                currency="AED",
                features=["leads", "pipeline", "workflows", "reporting"],
            )
            db.add(plan)
            db.flush()

        existing_subscription = db.query(Subscription).filter_by(tenant_id=tenant.id).one_or_none()
        if existing_subscription is None:
            db.add(Subscription(tenant_id=tenant.id, plan_id=plan.id, status="active"))

        db.commit()
        logger.info("seed.completed")
        print("Seed complete.")
        print(f"  Platform super admin: {PLATFORM_SUPER_ADMIN_EMAIL}")
        print(f"    password: {PLATFORM_SUPER_ADMIN_PASSWORD}")
        print(f"  Demo tenant: {DEMO_TENANT_NAME} ({DEMO_TENANT_SLUG})")
        for demo_user in DEMO_USERS:
            print(f"    {demo_user['role_slug']}: {demo_user['email']} / {demo_user['password']}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    configure_logging()
    seed()
