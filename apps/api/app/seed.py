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

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import configure_logging, get_logger
from app.core.pipeline_stages import DEFAULT_SERVICES
from app.core.roles import DEFAULT_ROLE_BY_SLUG
from app.core.security import hash_password
from app.db.base import utcnow
from app.db.session import SessionLocal
from app.models.appointment import Appointment
from app.models.lead import Lead
from app.models.subscription import Subscription, SubscriptionPlan
from app.repositories.membership import MembershipRepository
from app.repositories.pipeline import PipelineStageRepository
from app.repositories.role import RoleRepository
from app.repositories.service import ServiceRepository
from app.repositories.tenant import TenantRepository
from app.repositories.user import UserRepository
from app.services.appointment_service import AppointmentService
from app.services.assignment_service import AssignmentService
from app.services.availability_service import DEFAULT_BUSINESS_HOURS
from app.services.catalog_service import slugify
from app.services.lead_service import LeadService
from app.services.message_template_service import MessageTemplateService
from app.services.scoring_service import ScoringService
from app.services.task_service import TaskService

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


DEFAULT_DEMO_SCORING_RULES: list[dict[str, Any]] = [
    {
        "name": "[DEMO] High estimated value",
        "rule_type": "estimated_value_at_least",
        "config": {"min_value": 15000},
        "points": 30,
    },
    {
        "name": "[DEMO] Consent given",
        "rule_type": "consent_given",
        "config": {},
        "points": 15,
    },
    {
        "name": "[DEMO] Complete contact info",
        "rule_type": "complete_contact_info",
        "config": {},
        "points": 15,
    },
    {
        "name": "[DEMO] Repeat enquiry",
        "rule_type": "repeat_enquiry",
        "config": {},
        "points": 20,
    },
]


def _seed_scoring_rules(db: Session, tenant_id: uuid.UUID) -> None:
    scoring = ScoringService(db)
    for index, rule in enumerate(DEFAULT_DEMO_SCORING_RULES):
        scoring.create_rule(
            tenant_id,
            name=rule["name"],
            rule_type=rule["rule_type"],
            config=rule["config"],
            points=rule["points"],
            sort_order=index,
        )


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

        # System roles (is_system=True) are owned by the product, not the
        # tenant, so re-sync their permission grants to the current
        # DEFAULT_ROLES definition on every run. This backfills a demo
        # tenant created before a milestone that added new permissions
        # (e.g. scoring.manage in M3) without touching any custom role a
        # tenant admin created themselves.
        for slug, role in role_map.items():
            default_role = DEFAULT_ROLE_BY_SLUG.get(slug)
            if role.is_system and default_role is not None:
                roles.update_permissions(role, list(default_role.permissions))

        # M4: business hours drive the booking availability engine: back
        # fill the standard UAE working week for any tenant that doesn't
        # have hours configured yet (fresh tenants included).
        settings = tenants.get_settings(tenant.id)
        if settings is not None and not settings.business_hours:
            settings.business_hours = DEFAULT_BUSINESS_HOURS

        # M3 additions run unconditionally (each is independently idempotent)
        # so an existing demo tenant seeded before Milestone 3 gets backfilled
        # instead of only new tenants getting scoring/templates/task types.
        if not ScoringService(db).list_rules(tenant.id):
            _seed_scoring_rules(db, tenant.id)
        MessageTemplateService(db).seed_defaults_for_tenant(tenant.id)
        if not TaskService(db).list_task_types(tenant.id):
            for type_name in ("Callback", "Document Collection", "Site Visit"):
                TaskService(db).create_task_type(tenant.id, name=type_name)

        owner_user = None
        membership_by_role: dict[str, Any] = {}
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
            membership = memberships.get_for_user_and_tenant(user.id, tenant.id)
            if membership is None:
                role = role_map[demo_user["role_slug"]]
                membership = memberships.create(
                    tenant_id=tenant.id, user_id=user.id, role_id=role.id
                )
                logger.info(
                    "seed.member_created",
                    extra={"extra_fields": {"email": user.email, "role": demo_user["role_slug"]}},
                )
            membership_by_role[demo_user["role_slug"]] = membership

        if not AssignmentService(db).list_rules(tenant.id):
            round_robin_members = [
                str(membership_by_role[slug].id)
                for slug in ("sales_agent", "manager")
                if slug in membership_by_role
            ]
            if round_robin_members:
                AssignmentService(db).create_rule(
                    tenant.id,
                    name="[DEMO] Round robin between sales staff",
                    strategy="round_robin",
                    config={"membership_ids": round_robin_members},
                    sort_order=0,
                )
                logger.info("seed.assignment_rule_created")

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
                # The scoring engine (Module 7) recomputes priority from the
                # active scoring rules on every create(); re-assert the
                # curated demo priority afterwards so the demo pipeline
                # board shows a deliberate spread of hot/warm/standard/low
                # leads rather than whatever the seeded rules compute.
                lead_service.update(
                    tenant.id,
                    lead.id,
                    actor_user_id=owner_user.id,
                    priority=demo_lead["priority"],
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

        # M4: demo appointments reference the demo leads above by last name,
        # so this runs unconditionally (guarded by its own existence check)
        # rather than only inside the fresh-lead-creation branch - a demo
        # tenant seeded before Milestone 4 already has the leads but no
        # appointments yet.
        if not db.query(Appointment).filter_by(tenant_id=tenant.id).first():
            sales_membership = membership_by_role.get("sales_agent")
            khalid = (
                db.query(Lead).filter_by(tenant_id=tenant.id, last_name="Khalid Al Suwaidi").first()
            )
            david = db.query(Lead).filter_by(tenant_id=tenant.id, last_name="David Chen").first()
            if sales_membership is not None and khalid is not None and david is not None:
                appointment_service = AppointmentService(db)
                upcoming = appointment_service.create(
                    tenant.id,
                    created_by_user_id=owner_user.id if owner_user else None,
                    lead_id=khalid.id,
                    assigned_membership_id=sales_membership.id,
                    service_id=khalid.service_id,
                    starts_at=utcnow() + timedelta(days=2, hours=10),
                    ends_at=utcnow() + timedelta(days=2, hours=11),
                    notes="[DEMO DATA] Initial consultation call.",
                )
                appointment_service.confirm(tenant.id, upcoming.id)

                past_starts_at = utcnow() - timedelta(days=5)
                past = appointment_service.create(
                    tenant.id,
                    created_by_user_id=owner_user.id if owner_user else None,
                    lead_id=david.id,
                    assigned_membership_id=sales_membership.id,
                    service_id=david.service_id,
                    starts_at=past_starts_at,
                    ends_at=past_starts_at + timedelta(hours=1),
                    notes="[DEMO DATA] Onboarding kickoff meeting.",
                )
                appointment_service.complete(tenant.id, past.id)
                logger.info("seed.demo_appointments_created")

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
