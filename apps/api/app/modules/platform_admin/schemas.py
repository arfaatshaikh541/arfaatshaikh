import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.subscriptions.models import FeatureType
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


# --- Catalog management (Milestone 9) ------------------------------------

class CreateModuleRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=500)


class UpdateModuleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=500)


class ModuleDetail(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str

    model_config = {"from_attributes": True}


class CreateFeatureRequest(BaseModel):
    module_id: uuid.UUID
    code: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=150)
    feature_type: FeatureType


class UpdateFeatureRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)


class FeatureDetail(BaseModel):
    id: uuid.UUID
    module_id: uuid.UUID
    module_code: str
    code: str
    name: str
    feature_type: FeatureType

    model_config = {"from_attributes": True}


class CreatePlanRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=500)
    is_custom: bool = False


class UpdatePlanRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=500)


class SetPlanActiveRequest(BaseModel):
    is_active: bool


class PlanDetail(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str
    is_custom: bool
    is_active: bool

    model_config = {"from_attributes": True}


class SetPlanFeatureRequest(BaseModel):
    feature_code: str
    enabled: bool = True
    limit: int | None = Field(default=None, ge=0)


class PlanFeatureDetail(BaseModel):
    feature_code: str
    feature_name: str
    module_code: str
    feature_type: FeatureType
    config: dict


class CreateAddOnRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=150)
    grants: dict = Field(default_factory=dict)


class UpdateAddOnRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    grants: dict = Field(default_factory=dict)


class AddOnDetail(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    grants: dict

    model_config = {"from_attributes": True}


class CreateUsageMetricRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=150)
    unit: str = Field(default="count", max_length=30)


class UpdateUsageMetricRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    unit: str = Field(default="count", max_length=30)


class UsageMetricDetail(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    unit: str

    model_config = {"from_attributes": True}
