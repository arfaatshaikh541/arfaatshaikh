import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.tenancy.models import TenantStatus


class CreateTenantRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=100)
    plan_code: str = Field(default="starter")
    owner_email: str
    owner_first_name: str = Field(min_length=1, max_length=100)
    owner_last_name: str = Field(min_length=1, max_length=100)


class TenantSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: TenantStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class SetTenantStatusRequest(BaseModel):
    status: TenantStatus


class AssignPlanRequest(BaseModel):
    plan_code: str
    trial_ends_at: datetime | None = None


class GrantAddOnRequest(BaseModel):
    add_on_code: str
    ends_at: datetime | None = None


class GrantFeatureOverrideRequest(BaseModel):
    feature_code: str
    config: dict
    expires_at: datetime | None = None
    reason: str = ""


class UsageSummaryItem(BaseModel):
    metric_code: str
    value: int


class SupportAccessRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    resource: str = Field(min_length=1, max_length=255)
