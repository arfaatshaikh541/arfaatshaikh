from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FindingListItem(BaseModel):
    id: uuid.UUID
    rule_key: str
    title: str
    category: str
    severity: str
    status: str
    risk_score: int
    asset_id: uuid.UUID
    asset_display_name: str
    asset_criticality: str
    assigned_to_user_id: uuid.UUID | None
    first_observed_at: datetime
    last_observed_at: datetime


class FindingDetail(FindingListItem):
    description: str
    evidence: dict
    resolution_note: str | None
    accepted_risk_expires_at: datetime | None
    closed_at: datetime | None


class FindingActivityRead(BaseModel):
    actor_label: str
    action: str
    context: dict
    created_at: datetime


class RiskSummaryRead(BaseModel):
    security_score: int
    open_findings_total: int
    open_findings_by_severity: dict[str, int]


class AssignFindingRequest(BaseModel):
    user_id: uuid.UUID


class AcceptRiskRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)
    expires_at: datetime | None = None


class RemediateFindingRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class DismissFindingRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class CorrelateTriggerResponse(BaseModel):
    task_id: str
