"""Idempotent development/demo seed script.

Run with: python -m app.db.seed.run

Creates (or leaves untouched if already present):
  - the full permission catalog (tenant + platform permissions)
  - the module/feature catalog and subscription plans/add-ons
  - usage metrics
  - a platform super admin account
  - a demo tenant ("Rafana Advisory Demo") on the Growth plan with three
    demo users (Tenant Owner, Manager, Sales Agent)

All demo-tenant data is clearly fictional and is labelled as such in the
tenant name and user names below. Nothing here is real personal
information.
"""
import logging

from app.core.config import get_settings
from app.core.db import session_scope, set_rls_context
from app.core.security import hash_password
from app.db.seed.catalog import ADD_ONS, MODULES, PLANS, USAGE_METRICS
from app.modules.entitlements.repository import UsageMetricRepository
from app.modules.identity.models import MembershipStatus
from app.modules.identity.repository import MembershipRepository, UserRepository
from app.modules.permissions.catalog import ALL_PERMISSIONS
from app.modules.permissions.repository import PermissionRepository
from app.modules.permissions.service import provision_default_roles_for_tenant
from app.modules.subscriptions.models import FeatureType
from app.modules.subscriptions.repository import (
    AddOnRepository,
    FeatureRepository,
    ModuleRepository,
    PlanRepository,
)
from app.modules.subscriptions.service import assign_plan
from app.modules.tenancy.repository import TenantRepository

logger = logging.getLogger("app.seed")
settings = get_settings()


def seed_permissions(db) -> None:
    repo = PermissionRepository(db)
    for code, description in ALL_PERMISSIONS.items():
        if repo.get_by_code(code) is None:
            is_platform = code.startswith("platform.")
            repo.create(code=code, description=description, is_platform_permission=is_platform)
    logger.info("Seeded %d permissions", len(ALL_PERMISSIONS))


def seed_modules_and_features(db) -> dict[str, dict[str, object]]:
    module_repo = ModuleRepository(db)
    feature_repo = FeatureRepository(db)
    feature_ids_by_code: dict[str, dict[str, object]] = {}

    for module_code, module_def in MODULES.items():
        module = module_repo.get_by_code(module_code)
        if module is None:
            module = module_repo.create(code=module_code, name=module_def["name"], description=module_def["description"])
        for feature_code, feature_def in module_def["features"].items():
            feature = feature_repo.get_by_code(module.id, feature_code)
            if feature is None:
                feature_type = FeatureType.BOOLEAN if feature_def["type"] == "boolean" else FeatureType.LIMIT
                feature = feature_repo.create(module_id=module.id, code=feature_code, name=feature_def["name"], feature_type=feature_type)
            feature_ids_by_code[feature_code] = {"id": feature.id, "module_code": module_code}
    logger.info("Seeded %d modules", len(MODULES))
    return feature_ids_by_code


def seed_usage_metrics(db) -> None:
    repo = UsageMetricRepository(db)
    for code, definition in USAGE_METRICS.items():
        if repo.get_by_code(code) is None:
            repo.create(code=code, name=definition["name"], unit=definition["unit"])
    logger.info("Seeded %d usage metrics", len(USAGE_METRICS))


def seed_plans(db, feature_ids_by_code: dict[str, dict[str, object]]) -> None:
    plan_repo = PlanRepository(db)
    for plan_code, plan_def in PLANS.items():
        plan = plan_repo.get_by_code(plan_code)
        if plan is None:
            plan = plan_repo.create(
                code=plan_code, name=plan_def["name"], description=plan_def["description"],
                is_custom=plan_def.get("is_custom", False),
            )
        for feature_code, config in plan_def["features"].items():
            feature_id = feature_ids_by_code[feature_code]["id"]
            plan_repo.set_feature_config(plan.id, feature_id, config)
    logger.info("Seeded %d subscription plans", len(PLANS))


def seed_add_ons(db) -> None:
    repo = AddOnRepository(db)
    for code, definition in ADD_ONS.items():
        if repo.get_by_code(code) is None:
            repo.create(code=code, name=definition["name"], grants=definition["grants"])
    logger.info("Seeded %d add-ons", len(ADD_ONS))


def seed_platform_admin(db) -> None:
    user_repo = UserRepository(db)
    existing = user_repo.get_by_email(settings.seed_platform_admin_email)
    if existing is not None:
        logger.info("Platform admin already exists: %s", settings.seed_platform_admin_email)
        return
    user = user_repo.create(
        email=settings.seed_platform_admin_email,
        password_hash=hash_password(settings.seed_platform_admin_password),
        first_name="Platform",
        last_name="Admin",
    )
    user.email_verified = True
    user.is_platform_admin = True
    logger.info("Created platform admin: %s", settings.seed_platform_admin_email)


def seed_demo_tenant(db) -> None:
    tenant_repo = TenantRepository(db)
    existing = tenant_repo.get_by_slug(settings.seed_demo_tenant_slug)
    if existing is not None:
        logger.info("Demo tenant already exists: %s", settings.seed_demo_tenant_slug)
        return

    tenant = tenant_repo.create(name="Rafana Advisory Demo (Fictional Demo Data)", slug=settings.seed_demo_tenant_slug)
    set_rls_context(db, tenant_id=tenant.id, is_platform_admin=True)

    roles = provision_default_roles_for_tenant(db, tenant.id)
    assign_plan(db, tenant_id=tenant.id, plan_code="growth", changed_by=None)

    user_repo = UserRepository(db)
    membership_repo = MembershipRepository(db)

    demo_users = [
        ("owner@rafana-demo.internal", "Demo", "Owner", "Tenant Owner"),
        ("manager@rafana-demo.internal", "Demo", "Manager", "Manager"),
        ("agent@rafana-demo.internal", "Demo", "Sales Agent", "Sales Agent"),
    ]
    for email, first_name, last_name, role_name in demo_users:
        user = user_repo.get_by_email(email)
        if user is None:
            user = user_repo.create(
                email=email, password_hash=hash_password(settings.seed_platform_admin_password),
                first_name=first_name, last_name=last_name,
            )
            user.email_verified = True
        membership_repo.create(tenant_id=tenant.id, user_id=user.id, role_id=roles[role_name].id, status=MembershipStatus.ACTIVE)

    logger.info("Created demo tenant '%s' with %d users", tenant.name, len(demo_users))


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    with session_scope() as db:
        set_rls_context(db, tenant_id=None, is_platform_admin=True)
        seed_permissions(db)
        feature_ids_by_code = seed_modules_and_features(db)
        seed_usage_metrics(db)
        seed_plans(db, feature_ids_by_code)
        seed_add_ons(db)
        seed_platform_admin(db)
        seed_demo_tenant(db)
    logger.info("Seed complete.")


if __name__ == "__main__":
    run()
