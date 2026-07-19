import uuid
from datetime import datetime

from pydantic import BaseModel


class SubscriptionResponse(BaseModel):
    tenant_id: uuid.UUID
    plan_key: str
    plan_name: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    entitlements: dict


class PlanResponse(BaseModel):
    key: str
    name: str
    description: str
    monthly_price_usd: float
    monthly_credit_grant: int
    checkout_available: bool


class PlanListResponse(BaseModel):
    plans: list[PlanResponse]
