import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.subscription import Subscription, SubscriptionPlan


class SubscriptionPlanRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self, *, active_only: bool = False) -> list[SubscriptionPlan]:
        stmt = select(SubscriptionPlan).order_by(SubscriptionPlan.price_cents)
        if active_only:
            stmt = stmt.where(SubscriptionPlan.is_active.is_(True))
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id(self, plan_id: uuid.UUID) -> SubscriptionPlan | None:
        return self.db.get(SubscriptionPlan, plan_id)

    def get_by_code(self, code: str) -> SubscriptionPlan | None:
        stmt = select(SubscriptionPlan).where(SubscriptionPlan.code == code)
        return self.db.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        code: str,
        name: str,
        price_cents: int,
        currency: str,
        features: list,
    ) -> SubscriptionPlan:
        plan = SubscriptionPlan(
            code=code, name=name, price_cents=price_cents, currency=currency, features=features
        )
        self.db.add(plan)
        self.db.flush()
        return plan

    def update(self, plan: SubscriptionPlan, **fields: object) -> SubscriptionPlan:
        for key, value in fields.items():
            if value is not None:
                setattr(plan, key, value)
        self.db.flush()
        return plan


class SubscriptionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_tenant(self, tenant_id: uuid.UUID) -> Subscription | None:
        stmt = select(Subscription).where(Subscription.tenant_id == tenant_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create(
        self, *, tenant_id: uuid.UUID, plan_id: uuid.UUID, status: str = "trialing"
    ) -> Subscription:
        subscription = Subscription(tenant_id=tenant_id, plan_id=plan_id, status=status)
        self.db.add(subscription)
        self.db.flush()
        return subscription

    def update(self, subscription: Subscription, **fields: object) -> Subscription:
        for key, value in fields.items():
            if value is not None:
                setattr(subscription, key, value)
        self.db.flush()
        return subscription
