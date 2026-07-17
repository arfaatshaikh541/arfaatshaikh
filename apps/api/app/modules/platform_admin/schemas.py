import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TenantSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str
    created_at: datetime


class GrantSupportAccessRequest(BaseModel):
    tenant_id: uuid.UUID
    platform_user_id: uuid.UUID
    reason: str = Field(min_length=3, max_length=500)
    duration_hours: int = Field(default=8, ge=1, le=72)


class SupportAccessGrantResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    platform_user_id: uuid.UUID
    reason: str
    expires_at: datetime
    revoked_at: datetime | None


class PlatformAuditLogResponse(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    tenant_id: uuid.UUID | None
    resource_type: str | None
    resource_id: str | None
    created_at: datetime
