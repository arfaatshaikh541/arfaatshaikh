from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AutomationSettingRead(BaseModel):
    mode: str


class AutomationSettingUpdateRequest(BaseModel):
    mode: str = Field(pattern="^(observe|guided|balanced|autopilot|lockdown)$")


class PlaybookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    rule_key: str
    action_key: str
    is_enabled: bool
    created_at: datetime


class PlaybookCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=2000)
    rule_key: str = Field(min_length=2, max_length=80)
    action_key: str = Field(min_length=2, max_length=80)
    is_enabled: bool = True


class PlaybookUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    rule_key: str | None = Field(default=None, min_length=2, max_length=80)
    action_key: str | None = Field(default=None, min_length=2, max_length=80)
    is_enabled: bool | None = None


class ActionCatalogEntry(BaseModel):
    action_key: str
    name: str
    safety_class: int
    reversible: bool


class ActionRunRead(BaseModel):
    id: uuid.UUID
    action_key: str
    provider_id: str
    safety_class: int
    status: str
    trigger: str
    asset_id: uuid.UUID
    asset_display_name: str
    finding_id: uuid.UUID | None
    playbook_id: uuid.UUID | None
    params: dict
    result_message: str | None
    requested_at: datetime
    decided_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None


class ExecuteActionRequest(BaseModel):
    asset_id: uuid.UUID
    action_key: str = Field(min_length=1, max_length=80)
    params: dict = Field(default_factory=dict)
    finding_id: uuid.UUID | None = None


class RejectActionRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class RunActionResponse(BaseModel):
    action_run: ActionRunRead
    task_id: str | None
