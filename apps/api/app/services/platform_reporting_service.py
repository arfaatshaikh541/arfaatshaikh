"""Module 16: platform-wide analytics.

The platform-level sibling of Milestone 5's tenant-scoped
ReportingService - same live-aggregate, no-cache tradeoff, just
unscoped by tenant_id since a platform admin looks across every
tenant at once rather than within one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.lead import Lead
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.tenant import Tenant


@dataclass
class TenantStatusCount:
    status: str
    count: int


@dataclass
class SubscriptionStatusCount:
    status: str
    count: int


@dataclass
class PlanCount:
    plan_code: str
    count: int


@dataclass
class PlatformOverview:
    total_tenants: int
    total_leads: int
    total_appointments: int
    tenants_by_status: list[TenantStatusCount] = field(default_factory=list)
    subscriptions_by_status: list[SubscriptionStatusCount] = field(default_factory=list)
    subscriptions_by_plan: list[PlanCount] = field(default_factory=list)


class PlatformReportingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_overview(self) -> PlatformOverview:
        total_tenants = self.db.execute(select(func.count()).select_from(Tenant)).scalar_one()
        total_leads = self.db.execute(select(func.count()).select_from(Lead)).scalar_one()
        total_appointments = self.db.execute(
            select(func.count()).select_from(Appointment)
        ).scalar_one()

        tenants_by_status = [
            TenantStatusCount(status=status, count=int(count))
            for status, count in self.db.execute(
                select(Tenant.status, func.count(Tenant.id)).group_by(Tenant.status)
            ).all()
        ]
        subscriptions_by_status = [
            SubscriptionStatusCount(status=status, count=int(count))
            for status, count in self.db.execute(
                select(Subscription.status, func.count(Subscription.id)).group_by(
                    Subscription.status
                )
            ).all()
        ]
        subscriptions_by_plan = [
            PlanCount(plan_code=code, count=int(count))
            for code, count in self.db.execute(
                select(SubscriptionPlan.code, func.count(Subscription.id))
                .select_from(SubscriptionPlan)
                .outerjoin(Subscription, Subscription.plan_id == SubscriptionPlan.id)
                .group_by(SubscriptionPlan.code)
            ).all()
        ]

        return PlatformOverview(
            total_tenants=int(total_tenants),
            total_leads=int(total_leads),
            total_appointments=int(total_appointments),
            tenants_by_status=tenants_by_status,
            subscriptions_by_status=subscriptions_by_status,
            subscriptions_by_plan=subscriptions_by_plan,
        )
