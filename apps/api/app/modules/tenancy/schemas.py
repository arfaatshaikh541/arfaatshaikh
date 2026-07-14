import uuid

from pydantic import BaseModel, Field


class TenantSettingsResponse(BaseModel):
    tenant_id: uuid.UUID
    timezone: str
    currency: str
    branding: dict
    business_hours: dict

    model_config = {"from_attributes": True}


class UpdateTenantSettingsRequest(BaseModel):
    timezone: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    branding: dict | None = None
    business_hours: dict | None = None
