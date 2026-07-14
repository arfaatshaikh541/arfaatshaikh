import uuid

from pydantic import BaseModel, Field

from app.modules.assignment.models import AssignmentStrategy


class CreateAssignmentRuleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    strategy: AssignmentStrategy
    conditions: dict = Field(default_factory=dict)
    eligible_user_ids: list[uuid.UUID] = Field(default_factory=list)


class UpdateAssignmentRuleRequest(BaseModel):
    name: str | None = None
    strategy: AssignmentStrategy | None = None
    conditions: dict | None = None
    eligible_user_ids: list[uuid.UUID] | None = None
    is_active: bool | None = None


class ReorderAssignmentRulesRequest(BaseModel):
    rule_ids: list[uuid.UUID]
