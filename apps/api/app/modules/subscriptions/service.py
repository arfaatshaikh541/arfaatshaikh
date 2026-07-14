import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.audit.service import log_event, log_feature_change
from app.modules.subscriptions.models import (
    Module,
    SubscriptionPlan,
    SubscriptionStatus,
    TenantAddOn,
    TenantSubscription,
)
from app.modules.subscriptions.repository import (
    AddOnRepository,
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
