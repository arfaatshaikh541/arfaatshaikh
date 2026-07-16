from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TrustPassportSettingsRead(BaseModel):
    is_published: bool
    public_slug: str | None
    headline: str
    description: str
    show_compliance_frameworks: bool
    updated_at: datetime | None


class UpdateTrustPassportSettingsRequest(BaseModel):
    is_published: bool
    headline: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=2000)
    show_compliance_frameworks: bool = True


class PublicFrameworkStatus(BaseModel):
    name: str
    status_label: str


class PublicTrustPassportRead(BaseModel):
    headline: str
    description: str
    generated_at: datetime
    compliance_frameworks: list[PublicFrameworkStatus] | None
