from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CredentialCreateRequest(BaseModel):
    provider_key: str = Field(min_length=2, max_length=80)
    label: str = Field(min_length=2, max_length=120)
    secret: str = Field(min_length=1, max_length=20000)


class CredentialRotateRequest(BaseModel):
    secret: str = Field(min_length=1, max_length=20000)


class CredentialRead(BaseModel):
    """Deliberately excludes ciphertext/nonce/wrapped_dek/key_version —
    those fields are never serialised into any API response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_key: str
    label: str
    health_status: str
    last_used_at: datetime | None
    rotated_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
