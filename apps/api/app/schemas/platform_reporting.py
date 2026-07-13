from app.schemas.common import ORMModel


class TenantStatusCountOut(ORMModel):
    status: str
    count: int


class SubscriptionStatusCountOut(ORMModel):
    status: str
    count: int


class PlanCountOut(ORMModel):
    plan_code: str
    count: int


class PlatformOverviewOut(ORMModel):
    total_tenants: int
    total_leads: int
    total_appointments: int
    tenants_by_status: list[TenantStatusCountOut]
    subscriptions_by_status: list[SubscriptionStatusCountOut]
    subscriptions_by_plan: list[PlanCountOut]
