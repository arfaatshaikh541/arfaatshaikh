import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import (
    ConflictError,
    FeatureNotEnabledError,
    ModuleNotEnabledError,
    NotFoundError,
    UsageLimitExceededError,
)
from app.modules.audit.service import log_event, log_feature_change
from app.modules.entitlements.models import TenantFeatureOverride, UsageMetric
from app.modules.entitlements.repository import (
    FeatureOverrideRepository,
    UsageMetricRepository,
    UsageRecordRepository,
)
from app.modules.subscriptions.models import AddOn, Feature, Module
from app.modules.subscriptions.repository import (
    AddOnRepository,
    FeatureRepository,
    PlanRepository,
    TenantSubscriptionRepository,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class EntitlementSet:
    """The fully-resolved set of what a tenant may use right now — the
    single source of truth consulted by both `require_module`/
    `require_feature` (backend enforcement) and `/me/entitlements`
    (frontend UI hints). A feature/module absent from these dicts is not
    granted.
    """

    plan_code: str | None
    subscription_status: str | None
    modules: dict[str, bool] = field(default_factory=dict)
    features: dict[str, dict] = field(default_factory=dict)

    def module_enabled(self, module_code: str) -> bool:
        return self.modules.get(module_code, False)

    def feature_config(self, feature_code: str) -> dict | None:
        return self.features.get(feature_code)

    def feature_enabled(self, feature_code: str) -> bool:
        config = self.feature_config(feature_code)
        return bool(config and config.get("enabled", True))

    def feature_limit(self, feature_code: str) -> int | None:
        config = self.feature_config(feature_code)
        if config is None:
            return 0
        return config.get("limit")


def _all_features_with_module_code(db: Session) -> list[tuple[Feature, str]]:
    rows = db.execute(select(Feature, Module.code).join(Module, Feature.module_id == Module.id)).all()
    return [(feature, module_code) for feature, module_code in rows]


def resolve_entitlements(db: Session, tenant_id: uuid.UUID) -> EntitlementSet:
    now = _utcnow()
    subscription = TenantSubscriptionRepository(db).get_for_tenant(tenant_id)
    if subscription is None:
        return EntitlementSet(plan_code=None, subscription_status=None)

    plan_features = PlanRepository(db).list_plan_features(subscription.plan_id)
    feature_configs: dict[uuid.UUID, dict] = {pf.feature_id: pf.config for pf in plan_features}

    add_on_repo = AddOnRepository(db)
    feature_repo = FeatureRepository(db)
    for grant in add_on_repo.list_active_for_tenant(tenant_id, at=now):
        add_on = db.get(AddOn, grant.add_on_id)
        if add_on is None:
            continue
        for entry in add_on.grants.get("features", []):
            feature = feature_repo.get_by_global_code(entry["feature_code"])
            if feature is not None:
                feature_configs[feature.id] = entry.get("config", {"enabled": True})

    for override in FeatureOverrideRepository(db).list_active_for_tenant(tenant_id, at=now):
        feature_configs[override.feature_id] = override.config

    modules: dict[str, bool] = {}
    features: dict[str, dict] = {}
    for feature, module_code in _all_features_with_module_code(db):
        config = feature_configs.get(feature.id)
        if config is None:
            continue
        features[feature.code] = config
        # Convention: the module's own "access" feature shares its code
        # with the module (e.g. feature "crm" under module "crm").
        if feature.code == module_code:
            modules[module_code] = bool(config.get("enabled", False))

    plan = PlanRepository(db).get(subscription.plan_id)
    return EntitlementSet(
        plan_code=plan.code if plan else None,
        subscription_status=subscription.status.value,
        modules=modules,
        features=features,
    )


def assert_module_enabled(db: Session, tenant_id: uuid.UUID, module_code: str) -> None:
    entitlements = resolve_entitlements(db, tenant_id)
    if not entitlements.module_enabled(module_code):
        raise ModuleNotEnabledError(
            f"The '{module_code}' module is not enabled for this tenant's subscription.",
            code="module_not_enabled",
        )


def assert_feature_enabled(db: Session, tenant_id: uuid.UUID, feature_code: str) -> None:
    entitlements = resolve_entitlements(db, tenant_id)
    if not entitlements.feature_enabled(feature_code):
        raise FeatureNotEnabledError(
            f"The '{feature_code}' feature is not enabled for this tenant's subscription.",
            code="feature_not_enabled",
        )


def get_usage_limit(db: Session, tenant_id: uuid.UUID, feature_code: str) -> int | None:
    """Returns None for "unlimited", otherwise the numeric cap."""
    entitlements = resolve_entitlements(db, tenant_id)
    return entitlements.feature_limit(feature_code)


def current_month_period(at: datetime | None = None) -> date:
    at = at or _utcnow()
    return date(at.year, at.month, 1)


def get_current_usage(db: Session, tenant_id: uuid.UUID, metric_code: str) -> int:
    metric = UsageMetricRepository(db).get_by_code(metric_code)
    if metric is None:
        return 0
    return UsageRecordRepository(db).get_current(tenant_id, metric.id, current_month_period())


def check_and_increment_usage(db: Session, tenant_id: uuid.UUID, *, metric_code: str, feature_code: str, amount: int = 1) -> int:
    """Concurrency-safe check-then-increment for a hard-capped resource.

    Locks the tenant's current-period usage row (`SELECT ... FOR UPDATE`)
    for the duration of the surrounding transaction so two simultaneous
    requests cannot both read the same pre-increment value and both slip
    under the limit. Raises if the increment would exceed the resolved
    limit; otherwise commits the new value and returns it.
    """
    limit = get_usage_limit(db, tenant_id, feature_code)

    metric_repo = UsageMetricRepository(db)
    metric = metric_repo.get_by_code(metric_code)
    if metric is None:
        metric = metric_repo.create(code=metric_code, name=metric_code.replace("_", " ").title())

    record_repo = UsageRecordRepository(db)
    period = current_month_period()
    record = record_repo.get_or_create_for_update(tenant_id, metric.id, period)

    new_value = record.value + amount
    if limit is not None and new_value > limit:
        raise UsageLimitExceededError(
            f"This action would exceed your plan's limit for '{metric_code}' ({limit}).",
            code="usage_limit_exceeded",
        )
    record.value = new_value
    return new_value


def grant_feature_override(
    db: Session, *, tenant_id: uuid.UUID, feature_code: str, config: dict, granted_by: uuid.UUID | None,
    expires_at: datetime | None = None, reason: str = "",
) -> TenantFeatureOverride:
    feature = FeatureRepository(db).get_by_global_code(feature_code)
    if feature is None:
        raise NotFoundError(f"Unknown feature code '{feature_code}'.")

    override = FeatureOverrideRepository(db).create(
        tenant_id=tenant_id, feature_id=feature.id, config=config, granted_by=granted_by,
        expires_at=expires_at, reason=reason,
    )
    log_feature_change(
        db, tenant_id=tenant_id, changed_by=granted_by, change_type="feature_override_granted",
        details={"feature_code": feature_code, "config": config, "reason": reason},
    )
    log_event(
        db, tenant_id=tenant_id, actor_user_id=granted_by, action="entitlements.override_granted",
        entity_type="tenant_feature_override", entity_id=override.id, after={"feature_code": feature_code, "config": config},
    )
    return override


def increment_usage_unchecked(db: Session, tenant_id: uuid.UUID, *, metric_code: str, amount: int = 1) -> int:
    """Adjusts a usage counter without evaluating any limit — used for
    platform-admin-driven seat accounting (e.g. the tenant owner's own
    seat at tenant creation time, before a plan limit is even meaningful
    to enforce against an admin action)."""
    metric_repo = UsageMetricRepository(db)
    metric = metric_repo.get_by_code(metric_code)
    if metric is None:
        metric = metric_repo.create(code=metric_code, name=metric_code.replace("_", " ").title())
    record_repo = UsageRecordRepository(db)
    record = record_repo.get_or_create_for_update(tenant_id, metric.id, current_month_period())
    record.value += amount
    return record.value


def list_usage_metrics(db: Session) -> list[UsageMetric]:
    return UsageMetricRepository(db).list_all()


def create_usage_metric(db: Session, *, code: str, name: str, unit: str, created_by: uuid.UUID | None) -> UsageMetric:
    repo = UsageMetricRepository(db)
    if repo.get_by_code(code) is not None:
        raise ConflictError(f"A usage metric with code '{code}' already exists.", code="usage_metric_code_taken")
    metric = repo.create(code=code, name=name, unit=unit)
    log_event(
        db, tenant_id=None, actor_user_id=created_by, action="catalog.usage_metric_created",
        entity_type="usage_metric", entity_id=metric.id, after={"code": code, "name": name, "unit": unit},
    )
    return metric


def update_usage_metric(db: Session, *, metric_id: uuid.UUID, name: str, unit: str, updated_by: uuid.UUID | None) -> UsageMetric:
    repo = UsageMetricRepository(db)
    metric = repo.get(metric_id)
    if metric is None:
        raise NotFoundError("Usage metric not found.")
    before = {"name": metric.name, "unit": metric.unit}
    metric = repo.update(metric, name=name, unit=unit)
    log_event(
        db, tenant_id=None, actor_user_id=updated_by, action="catalog.usage_metric_updated",
        entity_type="usage_metric", entity_id=metric.id, before=before, after={"name": name, "unit": unit},
    )
    return metric


def cleanup_expired_overrides(db: Session) -> int:
    """Deletes feature overrides whose `expires_at` has passed. Called by
    the Celery beat schedule. Deleting (rather than leaving them in place)
    is safe because `resolve_entitlements` already treats an override
    with a past `expires_at` as inactive — this only reclaims storage and
    keeps the active-override list small."""
    expired = FeatureOverrideRepository(db).list_expired(before=_utcnow())
    for override in expired:
        FeatureOverrideRepository(db).delete(override)
    return len(expired)
