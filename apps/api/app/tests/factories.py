import uuid

from sqlalchemy.orm import Session

from app.core.db import set_rls_context
from app.core.security import hash_password
from app.db.seed.catalog import ADD_ONS, MODULES, PLANS, USAGE_METRICS
from app.modules.entitlements.repository import UsageMetricRepository
from app.modules.identity.models import MembershipStatus, User
from app.modules.identity.repository import MembershipRepository, UserRepository
from app.modules.permissions.catalog import ALL_PERMISSIONS
from app.modules.permissions.repository import PermissionRepository
from app.modules.permissions.service import provision_default_roles_for_tenant
from app.modules.subscriptions.models import FeatureType, SubscriptionStatus
from app.modules.subscriptions.repository import (
    AddOnRepository,
    FeatureRepository,
    ModuleRepository,
    PlanRepository,
)
from app.modules.subscriptions.service import assign_plan
from app.modules.tenancy.models import Tenant
from app.modules.tenancy.repository import TenantRepository


def seed_catalog(db: Session) -> None:
    """Seeds the same commercial-model catalog as `app.db.seed.run`, used
    at the start of every test so entitlement/plan behaviour is exercised
    against real seeded data rather than hand-rolled test-only shortcuts."""
    permission_repo = PermissionRepository(db)
    for code, description in ALL_PERMISSIONS.items():
        if permission_repo.get_by_code(code) is None:
            permission_repo.create(code=code, description=description, is_platform_permission=code.startswith("platform."))

    module_repo = ModuleRepository(db)
    feature_repo = FeatureRepository(db)
    feature_ids: dict[str, uuid.UUID] = {}
    for module_code, module_def in MODULES.items():
        module = module_repo.get_by_code(module_code)
        if module is None:
            module = module_repo.create(code=module_code, name=module_def["name"], description=module_def["description"])
        for feature_code, feature_def in module_def["features"].items():
            feature = feature_repo.get_by_code(module.id, feature_code)
            if feature is None:
                feature_type = FeatureType.BOOLEAN if feature_def["type"] == "boolean" else FeatureType.LIMIT
                feature = feature_repo.create(module_id=module.id, code=feature_code, name=feature_def["name"], feature_type=feature_type)
            feature_ids[feature_code] = feature.id

    metric_repo = UsageMetricRepository(db)
    for code, definition in USAGE_METRICS.items():
        if metric_repo.get_by_code(code) is None:
            metric_repo.create(code=code, name=definition["name"], unit=definition["unit"])

    plan_repo = PlanRepository(db)
    for plan_code, plan_def in PLANS.items():
        plan = plan_repo.get_by_code(plan_code)
        if plan is None:
            plan = plan_repo.create(code=plan_code, name=plan_def["name"], description=plan_def["description"], is_custom=plan_def.get("is_custom", False))
        for feature_code, config in plan_def["features"].items():
            plan_repo.set_feature_config(plan.id, feature_ids[feature_code], config)

    add_on_repo = AddOnRepository(db)
    for code, definition in ADD_ONS.items():
        if add_on_repo.get_by_code(code) is None:
            add_on_repo.create(code=code, name=definition["name"], grants=definition["grants"])


def create_platform_admin(db: Session, *, email: str = "platform-admin@test.internal", password: str = "PlatformAdmin!2345") -> User:
    user = UserRepository(db).create(email=email, password_hash=hash_password(password), first_name="Platform", last_name="Admin")
    user.email_verified = True
    user.is_platform_admin = True
    return user


def create_tenant_with_owner(
    db: Session, *, name: str = "Test Co", plan_code: str = "growth", owner_email: str = "owner@test.internal",
    owner_password: str = "OwnerPass!2345",
) -> tuple[Tenant, User]:
    """Provisions a tenant, its default roles, an active Tenant Owner
    membership, and a subscription — using the same building blocks as
    the real platform-admin create-tenant workflow, just with the
    password set directly instead of via the email-link flow (tested
    separately in the invitation/provisioning tests)."""
    set_rls_context(db, tenant_id=None, is_platform_admin=True)
    tenant = TenantRepository(db).create(name=name, slug=name.lower().replace(" ", "-") + "-" + uuid.uuid4().hex[:6])
    set_rls_context(db, tenant_id=tenant.id, is_platform_admin=True)

    roles = provision_default_roles_for_tenant(db, tenant.id)
    owner = UserRepository(db).create(email=owner_email, password_hash=hash_password(owner_password), first_name="Test", last_name="Owner")
    owner.email_verified = True
    MembershipRepository(db).create(tenant_id=tenant.id, user_id=owner.id, role_id=roles["Tenant Owner"].id, status=MembershipStatus.ACTIVE)

    assign_plan(db, tenant_id=tenant.id, plan_code=plan_code, changed_by=None, status=SubscriptionStatus.ACTIVE)
    return tenant, owner


def add_member(db: Session, *, tenant: Tenant, email: str, password: str, role_name: str) -> User:
    from app.modules.permissions.repository import RoleRepository

    role = RoleRepository(db).get_by_name(tenant.id, role_name)
    assert role is not None, f"role {role_name} not provisioned for tenant"
    user = UserRepository(db).create(email=email, password_hash=hash_password(password), first_name="Member", last_name=role_name)
    user.email_verified = True
    MembershipRepository(db).create(tenant_id=tenant.id, user_id=user.id, role_id=role.id, status=MembershipStatus.ACTIVE)
    return user
