import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.modules.audit.service import log_event, log_feature_change
from app.modules.subscriptions.models import (
    AddOn,
    Feature,
    FeatureType,
    Module,
    PlanFeature,
    SubscriptionPlan,
    SubscriptionStatus,
    TenantAddOn,
    TenantSubscription,
)
from app.modules.subscriptions.repository import (
    AddOnRepository,
    FeatureRepository,
    ModuleRepository,
    PlanRepository,
    TenantSubscriptionRepository,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def list_modules(db: Session) -> list[Module]:
    return ModuleRepository(db).list_all()


def list_active_plans(db: Session) -> list[SubscriptionPlan]:
    return PlanRepository(db).list_active()


def list_all_plans(db: Session) -> list[SubscriptionPlan]:
    return PlanRepository(db).list_all()


def list_all_features(db: Session) -> list[Feature]:
    return FeatureRepository(db).list_all()


def list_all_add_ons(db: Session) -> list[AddOn]:
    return AddOnRepository(db).list_all()


# --- Catalog management (Milestone 9: Platform Super Admin) -------------
#
# Modules and features are creatable and editable (name/description only)
# but never deletable through this layer: `Module.code`/`Feature.code`
# are referenced directly in application code (`require_module("...")`,
# `require_feature("...")` across nine modules), so removing one out from
# under running code would silently break those checks. A feature's
# `feature_type` is likewise immutable after creation, since existing
# `plan_features`/`tenant_feature_overrides`/`add_ons.grants` rows already
# store a config dict shaped for that type. Plans, add-ons, and usage
# metrics carry no such code-level reference and get full CRUD (plans and
# add-ons still can't be hard-deleted, since a plan is FK-`RESTRICT`ed by
# `tenant_subscriptions` — deactivating is the equivalent "stop offering
# this" action).

def create_module(db: Session, *, code: str, name: str, description: str, created_by: uuid.UUID | None) -> Module:
    repo = ModuleRepository(db)
    if repo.get_by_code(code) is not None:
        raise ConflictError(f"A module with code '{code}' already exists.", code="module_code_taken")
    module = repo.create(code=code, name=name, description=description)
    log_event(
        db, tenant_id=None, actor_user_id=created_by, action="catalog.module_created",
        entity_type="module", entity_id=module.id, after={"code": code, "name": name},
    )
    return module


def update_module(db: Session, *, module_id: uuid.UUID, name: str, description: str, updated_by: uuid.UUID | None) -> Module:
    repo = ModuleRepository(db)
    module = repo.get(module_id)
    if module is None:
        raise NotFoundError("Module not found.")
    before = {"name": module.name, "description": module.description}
    module = repo.update(module, name=name, description=description)
    log_event(
        db, tenant_id=None, actor_user_id=updated_by, action="catalog.module_updated",
        entity_type="module", entity_id=module.id, before=before, after={"name": name, "description": description},
    )
    return module


def create_feature(
    db: Session, *, module_id: uuid.UUID, code: str, name: str, feature_type: FeatureType, created_by: uuid.UUID | None
) -> Feature:
    module_repo = ModuleRepository(db)
    module = module_repo.get(module_id)
    if module is None:
        raise NotFoundError("Module not found.")

    feature_repo = FeatureRepository(db)
    if feature_repo.get_by_code(module_id, code) is not None:
        raise ConflictError(f"Module '{module.code}' already has a feature with code '{code}'.", code="feature_code_taken")

    feature = feature_repo.create(module_id=module_id, code=code, name=name, feature_type=feature_type)
    log_event(
        db, tenant_id=None, actor_user_id=created_by, action="catalog.feature_created",
        entity_type="feature", entity_id=feature.id,
        after={"module_code": module.code, "code": code, "name": name, "feature_type": feature_type.value},
    )
    return feature


def update_feature(db: Session, *, feature_id: uuid.UUID, name: str, updated_by: uuid.UUID | None) -> Feature:
    repo = FeatureRepository(db)
    feature = repo.get(feature_id)
    if feature is None:
        raise NotFoundError("Feature not found.")
    before = {"name": feature.name}
    feature = repo.update(feature, name=name)
    log_event(
        db, tenant_id=None, actor_user_id=updated_by, action="catalog.feature_updated",
        entity_type="feature", entity_id=feature.id, before=before, after={"name": name},
    )
    return feature


def create_plan(
    db: Session, *, code: str, name: str, description: str, is_custom: bool, created_by: uuid.UUID | None
) -> SubscriptionPlan:
    repo = PlanRepository(db)
    if repo.get_by_code(code) is not None:
        raise ConflictError(f"A plan with code '{code}' already exists.", code="plan_code_taken")
    plan = repo.create(code=code, name=name, description=description, is_custom=is_custom)
    log_event(
        db, tenant_id=None, actor_user_id=created_by, action="catalog.plan_created",
        entity_type="subscription_plan", entity_id=plan.id, after={"code": code, "name": name, "is_custom": is_custom},
    )
    return plan


def update_plan(db: Session, *, plan_id: uuid.UUID, name: str, description: str, updated_by: uuid.UUID | None) -> SubscriptionPlan:
    repo = PlanRepository(db)
    plan = repo.get(plan_id)
    if plan is None:
        raise NotFoundError("Plan not found.")
    before = {"name": plan.name, "description": plan.description}
    plan = repo.update(plan, name=name, description=description)
    log_event(
        db, tenant_id=None, actor_user_id=updated_by, action="catalog.plan_updated",
        entity_type="subscription_plan", entity_id=plan.id, before=before, after={"name": name, "description": description},
    )
    return plan


def set_plan_active(db: Session, *, plan_id: uuid.UUID, is_active: bool, updated_by: uuid.UUID | None) -> SubscriptionPlan:
    repo = PlanRepository(db)
    plan = repo.get(plan_id)
    if plan is None:
        raise NotFoundError("Plan not found.")
    before = {"is_active": plan.is_active}
    plan = repo.set_active(plan, is_active=is_active)
    log_event(
        db, tenant_id=None, actor_user_id=updated_by, action="catalog.plan_active_changed",
        entity_type="subscription_plan", entity_id=plan.id, before=before, after={"is_active": is_active},
    )
    return plan


def set_plan_feature(
    db: Session, *, plan_id: uuid.UUID, feature_code: str, enabled: bool, limit: int | None, updated_by: uuid.UUID | None
) -> PlanFeature:
    plan_repo = PlanRepository(db)
    plan = plan_repo.get(plan_id)
    if plan is None:
        raise NotFoundError("Plan not found.")

    feature = FeatureRepository(db).get_by_global_code(feature_code)
    if feature is None:
        raise NotFoundError(f"Unknown feature code '{feature_code}'.")

    if feature.feature_type == FeatureType.BOOLEAN:
        config: dict = {"enabled": enabled}
    else:
        config = {"limit": limit} if enabled else {"enabled": False}

    plan_feature = plan_repo.set_feature_config(plan_id, feature.id, config)
    log_event(
        db, tenant_id=None, actor_user_id=updated_by, action="catalog.plan_feature_set",
        entity_type="plan_feature", entity_id=plan_feature.id,
        after={"plan_code": plan.code, "feature_code": feature_code, "config": config},
    )
    return plan_feature


def remove_plan_feature(db: Session, *, plan_id: uuid.UUID, feature_code: str, updated_by: uuid.UUID | None) -> None:
    plan_repo = PlanRepository(db)
    plan = plan_repo.get(plan_id)
    if plan is None:
        raise NotFoundError("Plan not found.")

    feature = FeatureRepository(db).get_by_global_code(feature_code)
    if feature is None:
        raise NotFoundError(f"Unknown feature code '{feature_code}'.")

    removed = plan_repo.remove_feature(plan_id, feature.id)
    if not removed:
        raise NotFoundError(f"Plan '{plan.code}' does not currently grant '{feature_code}'.")
    log_event(
        db, tenant_id=None, actor_user_id=updated_by, action="catalog.plan_feature_removed",
        entity_type="plan_feature", entity_id=None, after={"plan_code": plan.code, "feature_code": feature_code},
    )


def create_add_on(db: Session, *, code: str, name: str, grants: dict, created_by: uuid.UUID | None) -> AddOn:
    repo = AddOnRepository(db)
    if repo.get_by_code(code) is not None:
        raise ConflictError(f"An add-on with code '{code}' already exists.", code="add_on_code_taken")
    add_on = repo.create(code=code, name=name, grants=grants)
    log_event(
        db, tenant_id=None, actor_user_id=created_by, action="catalog.add_on_created",
        entity_type="add_on", entity_id=add_on.id, after={"code": code, "name": name, "grants": grants},
    )
    return add_on


def update_add_on(db: Session, *, add_on_id: uuid.UUID, name: str, grants: dict, updated_by: uuid.UUID | None) -> AddOn:
    repo = AddOnRepository(db)
    add_on = repo.get(add_on_id)
    if add_on is None:
        raise NotFoundError("Add-on not found.")
    before = {"name": add_on.name, "grants": add_on.grants}
    add_on = repo.update(add_on, name=name, grants=grants)
    log_event(
        db, tenant_id=None, actor_user_id=updated_by, action="catalog.add_on_updated",
        entity_type="add_on", entity_id=add_on.id, before=before, after={"name": name, "grants": grants},
    )
    return add_on


def get_tenant_subscription(db: Session, tenant_id: uuid.UUID) -> TenantSubscription | None:
    return TenantSubscriptionRepository(db).get_for_tenant(tenant_id)


def assign_plan(
    db: Session, *, tenant_id: uuid.UUID, plan_code: str, changed_by: uuid.UUID | None,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE, trial_ends_at: datetime | None = None,
) -> TenantSubscription:
    """Creates or replaces the tenant's subscription. Never touches any
    tenant-owned data table — a plan change only changes which
    entitlements resolve to enabled going forward. Existing records are
    untouched, satisfying "downgrades must preserve existing data".
    """
    plan_repo = PlanRepository(db)
    plan = plan_repo.get_by_code(plan_code)
    if plan is None:
        raise NotFoundError(f"Unknown plan code '{plan_code}'.")

    sub_repo = TenantSubscriptionRepository(db)
    existing = sub_repo.get_for_tenant(tenant_id)
    before = {"plan_id": str(existing.plan_id), "status": existing.status.value} if existing else None

    if existing:
        existing.plan_id = plan.id
        existing.status = status
        existing.trial_ends_at = trial_ends_at
        subscription = existing
    else:
        subscription = sub_repo.create(tenant_id=tenant_id, plan_id=plan.id, status=status, trial_ends_at=trial_ends_at)

    log_feature_change(
        db, tenant_id=tenant_id, changed_by=changed_by, change_type="plan_assigned",
        details={"plan_code": plan_code, "status": status.value},
    )
    log_event(
        db, tenant_id=tenant_id, actor_user_id=changed_by, action="subscription.plan_assigned",
        entity_type="tenant_subscription", entity_id=subscription.id, before=before,
        after={"plan_id": str(plan.id), "status": status.value},
    )
    return subscription


def grant_add_on(
    db: Session, *, tenant_id: uuid.UUID, add_on_code: str, granted_by: uuid.UUID | None,
    starts_at: datetime | None = None, ends_at: datetime | None = None,
) -> TenantAddOn:
    add_on_repo = AddOnRepository(db)
    add_on = add_on_repo.get_by_code(add_on_code)
    if add_on is None:
        raise NotFoundError(f"Unknown add-on code '{add_on_code}'.")

    grant = add_on_repo.grant(tenant_id=tenant_id, add_on_id=add_on.id, starts_at=starts_at or _utcnow(), ends_at=ends_at)
    log_feature_change(
        db, tenant_id=tenant_id, changed_by=granted_by, change_type="add_on_granted",
        details={"add_on_code": add_on_code, "ends_at": ends_at.isoformat() if ends_at else None},
    )
    log_event(
        db, tenant_id=tenant_id, actor_user_id=granted_by, action="subscription.add_on_granted",
        entity_type="tenant_add_on", entity_id=grant.id, after={"add_on_code": add_on_code},
    )
    return grant
