import uuid

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ScoringRuleOut(ORMModel):
    id: uuid.UUID
    name: str
    rule_type: str
    config: dict
    points: int
    sort_order: int
    is_active: bool


class ScoringRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    rule_type: str
    config: dict = Field(default_factory=dict)
    points: int
    sort_order: int = 0


class ScoringRuleUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    points: int | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class TenantScoringSettingsOut(ORMModel):
    hot_threshold: int
    warm_threshold: int
    standard_threshold: int


class TenantScoringSettingsUpdate(BaseModel):
    hot_threshold: int | None = None
    warm_threshold: int | None = None
    standard_threshold: int | None = None
