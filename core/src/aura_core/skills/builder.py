"""DynamicSkillBuilder: the deliberately safe interpretation of "AURA can
create a new skill." A new Skill is a named, ordered composition of
CAPABILITIES THAT ALREADY EXIST AND ARE ALREADY GOVERNED -- never
generated, unreviewed code, and never a new execution path around the
Action Broker. This is a real, narrow scope decision: generating and
safely sandboxing genuinely novel executable code is a much larger,
separate security-sensitive undertaking (arbitrary code execution
authority is exactly the kind of thing this system's whole governance
model exists to prevent handing out casually) and is not what this
builder does.

Every step's capability_name is validated against the real
CapabilityRegistry before anything is persisted -- an unknown or
hallucinated capability name is rejected outright, named explicitly in
the error, never silently dropped or substituted with a guess.
"""
from __future__ import annotations

from ..capabilities.registry import CapabilityRegistry
from .models import SkillRecord, SkillStep
from .registry import SkillRegistry


class UnknownCapabilityError(ValueError):
    def __init__(self, unknown_names: list[str]) -> None:
        self.unknown_names = unknown_names
        super().__init__(f"unknown capability name(s), cannot build a skill around them: {', '.join(unknown_names)}")


class DynamicSkillBuilder:
    def __init__(self, capabilities: CapabilityRegistry, skills: SkillRegistry) -> None:
        self._capabilities = capabilities
        self._skills = skills

    def compose(
        self, name: str, description: str, domain: str, steps: list[SkillStep], created_by: str = "auto",
    ) -> SkillRecord:
        unknown = [step.capability_name for step in steps if self._capabilities.get(step.capability_name) is None]
        if unknown:
            raise UnknownCapabilityError(unknown)
        if not steps:
            raise ValueError("a skill needs at least one step")

        return self._skills.create(name=name, description=description, domain=domain, steps=steps, created_by=created_by)
