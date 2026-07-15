import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.subscriptions.models import (
    AddOn,
    Feature,
    Module,
    PlanFeature,
    SubscriptionPlan,
    TenantAddOn,
    TenantSubscription,
)


class ModuleRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_all(self) -> list[Module]:
        return list(self.db.execute(select(Module).order_by(Module.name)).scalars().all())

    def get(self, module_id: uuid.UUID) -> Module | None:
        return self.db.get(Module, module_id)

    def get_by_code(self, code: str) -> Module | None:
        return self.db.execute(select(Module).where(Module.code == code)).scalar_one_or_none()

    def create(self, *, code: str, name: str, description: str = "") -> Module:
        module = Module(code=code, name=name, description=description)
        self.db.add(module)
        self.db.flush()
        return module

    def update(self, module: Module, *, name: str, description: str) -> Module:
        module.name = name
        module.description = description
        self.db.flush()
        return module


class FeatureRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, feature_id: uuid.UUID) -> Feature | None:
        return self.db.get(Feature, feature_id)

    def get_by_code(self, module_id: uuid.UUID, code: str) -> Feature | None:
        return self.db.execute(
            select(Feature).where(Feature.module_id == module_id, Feature.code == code)
        ).scalar_one_or_none()

    def get_by_global_code(self, code: str) -> Feature | None:
        """Feature codes are unique per-module; this looks up the first
        match across modules, which is sufficient because our seeded
        catalog never reuses a bare code across modules."""
        return self.db.execute(select(Feature).where(Feature.code == code)).scalar_one_or_none()

    def list_for_module(self, module_id: uuid.UUID) -> list[Feature]:
        return list(self.db.execute(select(Feature).where(Feature.module_id == module_id)).scalars().all())

    def list_all(self) -> list[Feature]:
        return list(self.db.execute(select(Feature).order_by(Feature.name)).scalars().all())

    def create(self, *, module_id: uuid.UUID, code: str, name: str, feature_type) -> Feature:
        feature = Feature(module_id=module_id, code=code, name=name, feature_type=feature_type)
        self.db.add(feature)
        self.db.flush()
        return feature

    def update(self, feature: Feature, *, name: str) -> Feature:
        feature.name = name
        self.db.flush()
        return feature


class PlanRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, plan_id: uuid.UUID) -> SubscriptionPlan | None:
        return self.db.get(SubscriptionPlan, plan_id)

    def get_by_code(self, code: str) -> SubscriptionPlan | None:
        return self.db.execute(select(SubscriptionPlan).where(SubscriptionPlan.code == code)).scalar_one_or_none()

    def list_active(self) -> list[SubscriptionPlan]:
        return list(
            self.db.execute(select(SubscriptionPlan).where(SubscriptionPlan.is_active.is_(True))).scalars().all()
        )

    def list_all(self) -> list[SubscriptionPlan]:
        return list(self.db.execute(select(SubscriptionPlan).order_by(SubscriptionPlan.name)).scalars().all())

    def create(self, *, code: str, name: str, description: str = "", is_custom: bool = False) -> SubscriptionPlan:
        plan = SubscriptionPlan(code=code, name=name, description=description, is_custom=is_custom)
        self.db.add(plan)
        self.db.flush()
        return plan

    def update(self, plan: SubscriptionPlan, *, name: str, description: str) -> SubscriptionPlan:
        plan.name = name
        plan.description = description
        self.db.flush()
        return plan

    def set_active(self, plan: SubscriptionPlan, *, is_active: bool) -> SubscriptionPlan:
        plan.is_active = is_active
        self.db.flush()
        return plan

    def set_feature_config(self, plan_id: uuid.UUID, feature_id: uuid.UUID, config: dict) -> PlanFeature:
        existing = self.db.execute(
            select(PlanFeature).where(PlanFeature.plan_id == plan_id, PlanFeature.feature_id == feature_id)
        ).scalar_one_or_none()
        if existing:
            existing.config = config
            self.db.flush()
            return existing
        plan_feature = PlanFeature(plan_id=plan_id, feature_id=feature_id, config=config)
        self.db.add(plan_feature)
        self.db.flush()
        return plan_feature

    def remove_feature(self, plan_id: uuid.UUID, feature_id: uuid.UUID) -> bool:
        existing = self.db.execute(
            select(PlanFeature).where(PlanFeature.plan_id == plan_id, PlanFeature.feature_id == feature_id)
        ).scalar_one_or_none()
        if existing is None:
            return False
        self.db.delete(existing)
        self.db.flush()
        return True

    def list_plan_features(self, plan_id: uuid.UUID) -> list[PlanFeature]:
        return list(self.db.execute(select(PlanFeature).where(PlanFeature.plan_id == plan_id)).scalars().all())


class TenantSubscriptionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_tenant(self, tenant_id: uuid.UUID) -> TenantSubscription | None:
        return self.db.execute(
            select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_id)
        ).scalar_one_or_none()

    def create(self, *, tenant_id: uuid.UUID, plan_id: uuid.UUID, status, trial_ends_at=None) -> TenantSubscription:
        sub = TenantSubscription(tenant_id=tenant_id, plan_id=plan_id, status=status, trial_ends_at=trial_ends_at)
        self.db.add(sub)
        self.db.flush()
        return sub


class AddOnRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, add_on_id: uuid.UUID) -> AddOn | None:
        return self.db.get(AddOn, add_on_id)

    def get_by_code(self, code: str) -> AddOn | None:
        return self.db.execute(select(AddOn).where(AddOn.code == code)).scalar_one_or_none()

    def list_all(self) -> list[AddOn]:
        return list(self.db.execute(select(AddOn).order_by(AddOn.name)).scalars().all())

    def create(self, *, code: str, name: str, grants: dict) -> AddOn:
        add_on = AddOn(code=code, name=name, grants=grants)
        self.db.add(add_on)
        self.db.flush()
        return add_on

    def update(self, add_on: AddOn, *, name: str, grants: dict) -> AddOn:
        add_on.name = name
        add_on.grants = grants
        self.db.flush()
        return add_on

    def list_active_for_tenant(self, tenant_id: uuid.UUID, *, at) -> list[TenantAddOn]:
        return list(
            self.db.execute(
                select(TenantAddOn).where(
                    TenantAddOn.tenant_id == tenant_id,
                    TenantAddOn.starts_at <= at,
                    (TenantAddOn.ends_at.is_(None) | (TenantAddOn.ends_at > at)),
                )
            )
            .scalars()
            .all()
        )

    def grant(self, *, tenant_id: uuid.UUID, add_on_id: uuid.UUID, starts_at, ends_at=None) -> TenantAddOn:
        grant = TenantAddOn(tenant_id=tenant_id, add_on_id=add_on_id, starts_at=starts_at, ends_at=ends_at)
        self.db.add(grant)
        self.db.flush()
        return grant
