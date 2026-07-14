import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.modules.scoring.models import ScoringOperator


class CreateScoringRuleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    field: str = Field(min_length=1, max_length=150)
    operator: ScoringOperator
    value: Any = None
    points: int


class UpdateScoringRuleRequest(BaseModel):
    name: str | None = None
    field: str | None = None
    operator: ScoringOperator | None = None
    value: Any = None
    points: int | None = None
    is_active: bool | None = None


class ReorderScoringRulesRequest(BaseModel):
    rule_ids: list[uuid.UUID]


class UpdateScoringSettingsRequest(BaseModel):
    hot_threshold: int | None = None
    warm_threshold: int | None = None
    auto_priority: bool | None = None
