from typing import Any

from pydantic import BaseModel, Field

from app.modules.workflow_automation.conditions import ConditionOperator
from app.modules.workflow_automation.models import WorkflowActionType, WorkflowTriggerEvent


class ConditionInput(BaseModel):
    field: str
    operator: ConditionOperator
    value: Any = None


class CreateWorkflowRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str = ""
    trigger_event: WorkflowTriggerEvent
    trigger_config: dict = Field(default_factory=dict)
    conditions: list[ConditionInput] = Field(default_factory=list)


class UpdateWorkflowRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    trigger_config: dict | None = None
    conditions: list[ConditionInput] | None = None
    is_active: bool | None = None


class AddStepRequest(BaseModel):
    delay_minutes: int = Field(default=0, ge=0)
    action_type: WorkflowActionType
    action_config: dict = Field(default_factory=dict)
