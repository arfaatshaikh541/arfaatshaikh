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
    reason: str
    status: str
    starts_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
