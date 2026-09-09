"""Result types for the Universal Planner. A PlanResult is deliberately
split into `steps` (capability names the planner verified exist and are
available) and `gaps` (everything else) -- an unfamiliar or unresolved
part of a request is never silently dropped or guessed at, it's reported
in the exact structure the product brief's "Capability Gap Response"
section asks for.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlannedStep:
    capability_name: str
    params: dict = field(default_factory=dict)
    reasoning: str = ""


@dataclass(frozen=True)
class CapabilityGap:
    objective: str
    missing_capability: str
    required_tool: str = ""
    required_provider: str = ""
    required_permission: str = ""
    can_build_skill: bool = False
    next_action: str = ""

    def to_dict(self) -> dict:
        return {
            "OBJECTIVE": self.objective,
            "MISSING_CAPABILITY": self.missing_capability,
            "REQUIRED_TOOL": self.required_tool,
            "REQUIRED_PROVIDER": self.required_provider,
            "REQUIRED_PERMISSION": self.required_permission,
            "CAN_BUILD_SKILL": self.can_build_skill,
            "NEXT_ACTION": self.next_action,
        }


@dataclass
class PlanResult:
    objective: str
    available_capabilities: list[str] = field(default_factory=list)
    steps: list[PlannedStep] = field(default_factory=list)
    gaps: list[CapabilityGap] = field(default_factory=list)
    raw_response: str = ""

    @property
    def fully_resolved(self) -> bool:
        return len(self.steps) > 0 and len(self.gaps) == 0
