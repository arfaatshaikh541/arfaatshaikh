from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class LinkedFindingRead(BaseModel):
    id: uuid.UUID
    title: str
    rule_key: str
    severity: str
    status: str
    asset_display_name: str


class LinkedAssetRead(BaseModel):
    id: uuid.UUID
    display_name: str
    asset_type: str
    criticality: str


class IncidentListItem(BaseModel):
    id: uuid.UUID
    title: str
    severity: str
    status: str
    assigned_to_user_id: uuid.UUID | None
    finding_count: int
    asset_count: int
    declared_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None


class IncidentDetail(IncidentListItem):
    description: str
    declared_by_user_id: uuid.UUID | None
    closure_summary: str | None
    findings: list[LinkedFindingRead]
    assets: list[LinkedAssetRead]


class IncidentActivityRead(BaseModel):
    actor_label: str
    action: str
    context: dict
    created_at: datetime


class IncidentSummaryRead(BaseModel):
    open_incidents_total: int
    open_incidents_by_severity: dict[str, int]


class DeclareIncidentRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=5000)
    severity: str = Field(pattern="^(critical|high|medium|low)$")
    finding_ids: list[uuid.UUID] = Field(default_factory=list)
    asset_ids: list[uuid.UUID] = Field(default_factory=list)


class UpdateIncidentRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    severity: str | None = Field(default=None, pattern="^(critical|high|medium|low)$")
    assigned_to_user_id: uuid.UUID | None = None


class UpdateIncidentStatusRequest(BaseModel):
    status: str = Field(pattern="^(investigating|contained|resolved)$")


class AddIncidentNoteRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


class LinkFindingRequest(BaseModel):
    finding_id: uuid.UUID


class LinkAssetRequest(BaseModel):
    asset_id: uuid.UUID


class CloseIncidentRequest(BaseModel):
    closure_summary: str = Field(min_length=3, max_length=5000)
