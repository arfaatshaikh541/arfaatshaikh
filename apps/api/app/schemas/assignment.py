import uuid

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class AssignmentRuleOut(ORMModel):
    id: uuid.UUID
    name: str
    strategy: str
    config: dict
    sort_order: int
    is_active: bool
    fallback_membership_id: uuid.UUID | None


class AssignmentRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    strategy: str
    config: dict = Field(default_factory=dict)
    sort_order: int = 0
    fallback_membership_id: uuid.UUID | None = None


class AssignmentRuleUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    sort_order: int | None = None
    is_active: bool | None = None
    fallback_membership_id: uuid.UUID | None = None
