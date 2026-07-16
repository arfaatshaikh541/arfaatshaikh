from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class MatchedAssetRead(BaseModel):
    asset_id: uuid.UUID
    asset_display_name: str
    finding_id: uuid.UUID
    finding_status: str


class IndicatorRead(BaseModel):
    id: uuid.UUID
    indicator_type: str
    value: str
    confidence: float
    source: str
    first_seen_at: datetime
    last_seen_at: datetime
    matches: list[MatchedAssetRead]
