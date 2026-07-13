import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class WorkflowRuleOut(ORMModel):
    id: uuid.UUID
    name: str
    trigger_type: str
    conditions: list
    actions: list
    sort_order: int
    is_active: bool


class WorkflowRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    trigger_type: str
    conditions: list = Field(default_factory=list)
    actions: list = Field(default_factory=list)
    sort_order: int = 0


class WorkflowRuleUpdate(BaseModel):
    name: str | None = None
    conditions: list | None = None
    actions: list | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class WorkflowExecutionLogOut(ORMModel):
    id: uuid.UUID
    workflow_rule_id: uuid.UUID
    lead_id: uuid.UUID | None
    trigger_type: str
    actions_taken: list
    executed_at: datetime
