from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AssetListItem(BaseModel):
    id: uuid.UUID
    asset_type: str
    display_name: str
    source: str
    criticality: str
    exposure: str
    lifecycle_status: str
    last_observed_at: datetime


class AssetIdentifierRead(BaseModel):
    identifier_type: str
    identifier_value: str


class AssetRelationshipRead(BaseModel):
    relationship_type: str
    direction: str  # "outbound" | "inbound"
    related_asset_id: uuid.UUID
    related_asset_display_name: str
    source: str
    observed_at: datetime


class AssetChangeRead(BaseModel):
    field_name: str
    old_value: str | None
    new_value: str | None
    changed_at: datetime


class AssetOwnerRead(BaseModel):
    user_id: uuid.UUID
    email: str
    ownership_type: str


class AssetDetail(BaseModel):
    id: uuid.UUID
    asset_type: str
    display_name: str
    source: str
    confidence: float
    criticality: str
    exposure: str
    lifecycle_status: str
    attributes: dict
    last_observed_at: datetime
    last_assessed_at: datetime | None
    identifiers: list[AssetIdentifierRead]
    relationships: list[AssetRelationshipRead]
    owners: list[AssetOwnerRead]
    tags: dict[str, str]


class AssetCriticalityUpdate(BaseModel):
    criticality: str = Field(pattern="^(low|medium|high|critical)$")


class AssetOwnerAssignRequest(BaseModel):
    user_id: uuid.UUID
    ownership_type: str = Field(default="owner", max_length=40)
