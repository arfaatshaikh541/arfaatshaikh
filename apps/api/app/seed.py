"""Idempotent local/demo seed data.

Run with: python -m app.seed

Creates:
- A platform super admin account.
- A demo tenant, "Rafana Advisory Demo", with Owner / Manager / Sales Agent
  users, the default role set, default pipeline stages, the Professional
  Services template of services, and a handful of fictional demo leads.
- A demo subscription plan + active subscription for that tenant.

All demo data is fictional and clearly labeled with a "[DEMO]" prefix in
display names, per the product requirement that demo data never look like
real customer data. Safe to run multiple times - it checks for existing
rows before creating anything.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import configure_logging, get_logger
from app.core.pipeline_stages import DEFAULT_SERVICES
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.lead import Lead
from app.models.subscription import Subscription, SubscriptionPlan
from app.repositories.membership import MembershipRepository
from app.repositories.pipeline import PipelineStageRepository
from app.repositories.role import RoleRepository
from app.repositories.service import ServiceRepository
from app.repositories.tenant import TenantRepository
from app.repositories.user import UserRepository
from app.services.catalog_service import slugify
from app.services.lead_service import LeadService

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

DEMO_LEADS: list[dict[str, Any]] = [
    {
        "first_name": "[DEMO]",
        "last_name": "Khalid Al Suwaidi",
        "company": "Al Suwaidi Trading FZE",
        "email": "khalid@alsuwaiditrading-demo.example",
        "phone": "+971501234501",
        "service_name": "External Audit",
        "priority": "hot",
        "estimated_value": 25000,
        "consent_given": True,
        "utm_source": "google",
        "utm_campaign": "audit-season-2026",
        "stage_slug": "qualified",
    },
    {
        "first_name": "[DEMO]",
        "last_name": "Priya Nair",
        "company": "Nair Consulting Free Zone LLC",
        "email": "priya@nairconsulting-demo.example",
        "phone": "+971501234502",
        "service_name": "Corporate Tax",
        "priority": "warm",
        "estimated_value": 8000,
        "consent_given": True,
        "utm_source": "linkedin",
        "stage_slug": "contacted",
    },
    {
        "first_name": "[DEMO]",
        "last_name": "Omar Haddad",
        "company": "Haddad Business Setup Advisors",
        "email": "omar@haddadadvisors-demo.example",
        "phone": "+971501234503",
        "service_name": "Business Setup",
        "priority": "standard",
        "estimated_value": 15000,
        "consent_given": True,
        "utm_source": "referral",
        "stage_slug": "new",
    },
    {
        "first_name": "[DEMO]",
        "last_name": "Sara Al Mheiri",
        "company": "Al Mheiri Holdings",
        "email": "sara@almheiriholdings-demo.example",
        "phone": "+971501234504",
        "service_name": "VAT",
        "priority": "warm",
        "estimated_value": 6000,
        "consent_given": True,
        "utm_source": "google",
        "stage_slug": "proposal_sent",
    },
    {
        "first_name": "[DEMO]",
        "last_name": "David Chen",
        "company": "Chen Global Accounting",
        "email": "david@chenglobal-demo.example",
        "phone": "+971501234505",
        "service_name": "Accounting and Bookkeeping",
        "priority": "low_priority",
        "estimated_value": 3000,
        "consent_given": True,
        "utm_source": "direct",
        "stage_slug": "won",
    },
]


def seed() -> None:
    db = SessionLocal()
    try:
        users = UserRepository(db)
        tenants = TenantRepository(db)
        roles = RoleRepository(db)
        memberships = MembershipRepository(db)
        pipeline_stages = PipelineStageRepository(db)
        services_repo = ServiceRepository(db)

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
            pipeline_stages.create_defaults_for_tenant(tenant.id)
            for index, service_name in enumerate(DEFAULT_SERVICES):
                services_repo.create(
                    tenant_id=tenant.id,
                    name=service_name,
                    slug=slugify(service_name),
                    sort_order=index,
                )
            logger.info("seed.tenant_created", extra={"extra_fields": {"slug": tenant.slug}})
        else:
            role_map = {r.slug: r for r in roles.list_for_tenant(tenant.id)}
            logger.info("seed.tenant_exists")

        owner_user = None
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
            if demo_user["role_slug"] == "owner":
                owner_user = user
            existing_membership = memberships.get_for_user_and_tenant(user.id, tenant.id)
            if existing_membership is None:
                role = role_map[demo_user["role_slug"]]
                memberships.create(tenant_id=tenant.id, user_id=user.id, role_id=role.id)
                logger.info(
                    "seed.member_created",
                    extra={"extra_fields": {"email": user.email, "role": demo_user["role_slug"]}},
                )

        existing_lead_count = db.query(Lead).filter_by(tenant_id=tenant.id).count()
        if existing_lead_count == 0 and owner_user is not None:
            lead_service = LeadService(db)
            stage_by_slug = {s.slug: s for s in pipeline_stages.list_for_tenant(tenant.id)}
            service_by_name = {s.name: s for s in services_repo.list_for_tenant(tenant.id)}
            for demo_lead in DEMO_LEADS:
                lead = lead_service.create(
                    tenant.id,
                    actor_user_id=owner_user.id,
                    first_name=demo_lead["first_name"],
                    last_name=demo_lead["last_name"],
                    email=demo_lead["email"],
                    phone=demo_lead["phone"],
                    company=demo_lead["company"],
                    service_id=service_by_name[demo_lead["service_name"]].id,
                    priority=demo_lead["priority"],
                    estimated_value=demo_lead["estimated_value"],
                    consent_given=demo_lead["consent_given"],
                    consent_text_shown="[DEMO DATA] seeded consent record.",
                    utm={"utm_source": demo_lead.get("utm_source")},
                )
                target_stage = stage_by_slug.get(demo_lead["stage_slug"])
                if target_stage is not None and target_stage.id != lead.stage_id:
                    lead_service.change_stage(
                        tenant.id,
                        lead.id,
                        actor_user_id=owner_user.id,
                        to_stage_id=target_stage.id,
                    )
            logger.info(
                "seed.demo_leads_created", extra={"extra_fields": {"count": len(DEMO_LEADS)}}
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
