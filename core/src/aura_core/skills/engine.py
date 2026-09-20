"""SkillEngine: executes a persisted Skill's steps, in order, through the
real Action Broker -- exactly the same submit() path every other caller
in this codebase uses. Nothing here bypasses the kill switch, risk
classification, policy evaluation, approval, or audit logging a single
capability call would already go through; a Skill is only ever a
sequence of those same real calls.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..governance.action_broker import ActionBroker, ActionOutcome, OutcomeStatus
from ..governance.risk_engine import ActionRequest
from .models import SkillRecord

_PLACEHOLDER = re.compile(r"^\{\{(\w+)\}\}$")


def _resolve(value, context: dict):
    if isinstance(value, str):
        match = _PLACEHOLDER.match(value)
        if match:
            return context.get(match.group(1), value)
        return value
    if isinstance(value, dict):
        return {k: _resolve(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v, context) for v in value]
    return value


@dataclass
class StepResult:
    capability_name: str
    outcome: ActionOutcome


@dataclass
class SkillRunResult:
    skill_id: str
    skill_name: str
    step_results: list[StepResult] = field(default_factory=list)
    status: str = "completed"  # "completed" | "failed"

    @property
    def succeeded(self) -> bool:
        return self.status == "completed"


class SkillEngine:
    def __init__(self, broker: ActionBroker) -> None:
        self._broker = broker

    def run(self, skill: SkillRecord, context: dict | None = None, requested_by: str = "owner") -> SkillRunResult:
        context = context or {}
        result = SkillRunResult(skill_id=skill.id, skill_name=skill.name)

        for step in skill.steps():
            params = _resolve(step.params_template, context)
            outcome = self._broker.submit(ActionRequest(action_type=step.capability_name, params=params, requested_by=requested_by))
            result.step_results.append(StepResult(capability_name=step.capability_name, outcome=outcome))

            if outcome.status != OutcomeStatus.EXECUTED and step.on_failure == "abort":
                result.status = "failed"
                return result

        return result
