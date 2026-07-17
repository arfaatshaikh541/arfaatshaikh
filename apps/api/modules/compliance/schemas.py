from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ControlRead(BaseModel):
    id: uuid.UUID
    key: str
    title: str
    description: str
    status: str
    note: str | None
    updated_by_user_id: uuid.UUID | None
    updated_at: datetime | None


class FrameworkRead(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    description: str
    score: int
    controls: list[ControlRead]


class FrameworkScoreRead(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    score: int
    met_count: int
    total_count: int


class ComplianceSummaryRead(BaseModel):
    overall_score: int | None
    frameworks: list[FrameworkScoreRead]


class UpdateControlStatusRequest(BaseModel):
    status: str = Field(pattern="^(met|partial|not_met|not_applicable)$")
    note: str | None = Field(default=None, max_length=2000)


class EvidenceRead(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    evidence_type: str
    source_url: str | None
    target_type: str
    target_id: uuid.UUID
    collected_at: datetime
    created_by_user_id: uuid.UUID | None
    created_at: datetime
    file_name: str | None = None
    file_content_type: str | None = None
    file_size_bytes: int | None = None


class CreateEvidenceRequest(BaseModel):
    """`evidence_type` is restricted to `url`/`note` here — `document`
    evidence carries real file bytes that don't fit a JSON body, so it's
    created through the dedicated multipart upload route instead (see
    `POST /api/evidence/document` in routes.py)."""

    title: str = Field(min_length=2, max_length=300)
    description: str = Field(default="", max_length=2000)
    evidence_type: str = Field(pattern="^(url|note)$")
    source_url: str | None = Field(default=None, max_length=2000)
    target_type: str = Field(pattern="^(compliance_control|incident)$")
    target_id: uuid.UUID
    collected_at: datetime | None = None


class EvidenceExportRead(BaseModel):
    target_type: str
    target_id: uuid.UUID
    generated_at: datetime
    evidence: list[EvidenceRead]
