import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class SubscriptionPlanOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    price_cents: int
    currency: str
    features: list
    is_active: bool


class SubscriptionPlanCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    price_cents: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3, default="AED")
    features: list[str] = Field(default_factory=list)


class SubscriptionPlanUpdate(BaseModel):
    name: str | None = None
    price_cents: int | None = None
    currency: str | None = None
    features: list[str] | None = None
    is_active: bool | None = None


class SubscriptionOut(ORMModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    plan_id: uuid.UUID
    status: str
    current_period_end: datetime | None


class SubscriptionAssignRequest(BaseModel):
    plan_id: uuid.UUID
    status: str = "active"
