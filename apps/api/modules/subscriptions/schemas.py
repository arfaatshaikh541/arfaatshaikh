from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SubscriptionRead(BaseModel):
    plan_key: str
    plan_name: str
    status: str
    trial_ends_at: datetime | None
    current_period_end: datetime | None


class EntitlementsRead(BaseModel):
    entitled_modules: list[str]
    entitled_features: list[str]
    feature_limits: dict[str, int]
