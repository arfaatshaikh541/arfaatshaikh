from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class OnboardingRequest(BaseModel):
    organisation_name: str = Field(min_length=2, max_length=200)
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=12, max_length=200)


class OnboardingResponse(BaseModel):
    tenant_id: uuid.UUID
    tenant_slug: str
    user_id: uuid.UUID
    email_verification_required: bool = True


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    status: str
    industry: str | None
    is_demo: bool


class TenantSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    display_name: str | None
    timezone: str
    default_automation_mode: str


class TenantSettingsUpdate(BaseModel):
    display_name: str | None = None
    timezone: str | None = None
    default_automation_mode: str | None = Field(
        default=None, pattern="^(observe|guided|balanced|autopilot|lockdown)$"
    )


class TenantSecurityProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    require_mfa_for_admins: bool
    require_step_up_for_disruptive_actions: bool
    session_ttl_seconds: int


class TenantSecurityProfileUpdate(BaseModel):
    require_mfa_for_admins: bool | None = None
    require_step_up_for_disruptive_actions: bool | None = None
    session_ttl_seconds: int | None = Field(default=None, ge=300, le=604800)
