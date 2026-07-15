from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CatalogEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_id: str
    name: str
    category: str
    auth_method: str
    required_scopes: list[str]
    permission_risk: str
    supported_data_types: list[str]
    sync_modes: list[str]
    webhook_support: bool
    is_simulator: bool
    description: str


class TenantIntegrationCreateRequest(BaseModel):
    provider_id: str = Field(min_length=2, max_length=80)
    label: str = Field(min_length=2, max_length=120)
    secret: str = Field(min_length=1, max_length=20000)


class TenantIntegrationRead(BaseModel):
    id: uuid.UUID
    provider_id: str
    provider_name: str
    label: str
    status: str
    sync_mode: str
    last_synced_at: datetime | None
    created_at: datetime


class IntegrationHealthRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    message: str
    checked_at: datetime


class SyncRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    started_at: datetime
    completed_at: datetime | None
    records_processed: int
    records_created: int
    records_updated: int
    error_message: str | None


class TriggerSyncResponse(BaseModel):
    sync_run_id: uuid.UUID
    task_id: str
