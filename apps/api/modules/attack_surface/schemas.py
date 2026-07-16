from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DomainRead(BaseModel):
    id: uuid.UUID
    domain: str
    is_verified: bool
    verification_method: str | None
    verification_token: str | None
    verification_file_url: str
    verified_at: datetime | None
    created_at: datetime


class AddDomainRequest(BaseModel):
    domain: str = Field(min_length=3, max_length=255)


class VerifyDomainResult(BaseModel):
    domain: DomainRead
    verified_now: bool
    message: str
