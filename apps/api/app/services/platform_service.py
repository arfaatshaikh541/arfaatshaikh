from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.subscription import SUBSCRIPTION_STATUSES, Subscription, SubscriptionPlan
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.subscription import SubscriptionPlanRepository, SubscriptionRepository
from app.repositories.tenant import TenantRepository
from app.services.errors import ConflictError, NotFoundError, ValidationError


class PlatformService:
    """Platform super-admin operations. Every tenant-data access performed
    through this service is written to the immutable audit log, per
    docs/architecture/tenant-isolation-strategy.md."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.tenants = TenantRepository(db)
        self.audit = AuditLogRepository(db)
        self.plans = SubscriptionPlanRepository(db)
        self.subscriptions = SubscriptionRepository(db)

    def list_tenants(self, *, limit: int = 100, offset: int = 0) -> list[Tenant]:
        return self.tenants.list_all(limit=limit, offset=offset)

    def get_tenant_detail(self, *, actor: User, tenant_id: uuid.UUID) -> Tenant:
        tenant = self.tenants.get_by_id(tenant_id)
        if tenant is None:
            raise NotFoundError("Tenant not found.")
        self.audit.record(
            event_type="super_admin.tenant.viewed",
            tenant_id=tenant.id,
            actor_user_id=actor.id,
            entity_type="tenant",
            entity_id=str(tenant.id),
        )
        return tenant

    def set_tenant_status(
        self, *, actor: User, tenant_id: uuid.UUID, status: str, reason: str
    ) -> Tenant:
        tenant = self.tenants.get_by_id(tenant_id)
        if tenant is None:
            raise NotFoundError("Tenant not found.")
        previous_status = tenant.status
        tenant.status = status
        self.db.flush()
        self.audit.record(
            event_type="super_admin.tenant.status_changed",
            tenant_id=tenant.id,
            actor_user_id=actor.id,
            entity_type="tenant",
            entity_id=str(tenant.id),
            metadata={"from": previous_status, "to": status, "reason": reason},
        )
        return tenant

    # -- subscription plans --------------------------------------------

    def list_plans(self) -> list[SubscriptionPlan]:
        return self.plans.list_all()

    def create_plan(
        self, *, code: str, name: str, price_cents: int, currency: str, features: list
    ) -> SubscriptionPlan:
        if self.plans.get_by_code(code) is not None:
            raise ConflictError(f"A plan with code '{code}' already exists.")
        return self.plans.create(
            code=code, name=name, price_cents=price_cents, currency=currency, features=features
        )

    def update_plan(self, plan_id: uuid.UUID, **fields: object) -> SubscriptionPlan:
        plan = self.plans.get_by_id(plan_id)
        if plan is None:
            raise NotFoundError("Subscription plan not found.")
        return self.plans.update(plan, **fields)

    # -- tenant subscriptions --------------------------------------------

    def get_tenant_subscription(self, tenant_id: uuid.UUID) -> Subscription | None:
        if self.tenants.get_by_id(tenant_id) is None:
            raise NotFoundError("Tenant not found.")
        return self.subscriptions.get_for_tenant(tenant_id)

    def assign_subscription(
        self,
        *,
        actor: User,
        tenant_id: uuid.UUID,
        plan_id: uuid.UUID,
        status: str,
    ) -> Subscription:
        if self.tenants.get_by_id(tenant_id) is None:
            raise NotFoundError("Tenant not found.")
        if status not in SUBSCRIPTION_STATUSES:
            raise ValidationError(f"Unknown subscription status '{status}'.")
        plan = self.plans.get_by_id(plan_id)
        if plan is None:
            raise ValidationError("Subscription plan not found.")

        subscription = self.subscriptions.get_for_tenant(tenant_id)
        if subscription is None:
            subscription = self.subscriptions.create(
                tenant_id=tenant_id, plan_id=plan_id, status=status
            )
            from_plan_code: str | None = None
            from_status: str | None = None
        else:
            from_plan = self.plans.get_by_id(subscription.plan_id)
            from_plan_code = from_plan.code if from_plan else None
            from_status = subscription.status
            self.subscriptions.update(subscription, plan_id=plan_id, status=status)

        self.audit.record(
            event_type="super_admin.subscription.changed",
            tenant_id=tenant_id,
            actor_user_id=actor.id,
            entity_type="subscription",
            entity_id=str(subscription.id),
            metadata={
                "from_plan": from_plan_code,
                "to_plan": plan.code,
                "from_status": from_status,
                "to_status": status,
            },
        )
        return subscription
