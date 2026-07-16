from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SupportAccessGrantCreateRequest(BaseModel):
    tenant_id: uuid.UUID
    reason: str = Field(min_length=10, max_length=500)
    duration_hours: int = Field(default=4, ge=1, le=24)


class SupportAccessGrantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    platform_user_id: uuid.UUID
    platform_user_email: str | None = None
    requested_by_user_id: uuid.UUID
    requested_by_email: str | None = None
    approved_by_user_id: uuid.UUID | None
    approved_by_email: str | None = None
    reason: str
    status: str
    requested_duration_hours: int | None
    starts_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    revoked_reason: str | None


class TenantSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    status: str
    industry: str | None
    country_code: str | None
    is_demo: bool
    created_at: datetime


class UpdateTenantStatusRequest(BaseModel):
    status: str
    reason: str = Field(min_length=10, max_length=500)


class PlatformAuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    actor_label: str
    action: str
    target_type: str | None
    target_id: str | None
    context: dict
    created_at: datetime
