"""UniversalPlanner: decomposes a free-text objective into a sequence of
real, already-registered capabilities, using the same "constrain the
model's output to what's actually executable, never trust it blindly"
discipline as `executive.parse_plan()` and `email_intent.classify_message_intent()`.

The model is given the real list of currently-available capabilities
(from CapabilityRegistry.list_available() -- not the full static
catalog, so it never proposes something that isn't actually reachable in
this running process) and asked for a JSON array of steps. Every
resulting step is re-validated against that same list before being
returned as `PlanResult.steps` -- a step naming an unknown or
hallucinated capability is never executed, it becomes a `CapabilityGap`
instead, exactly like an objective the model itself flags as
unsupported. Nothing here executes anything; PlanResult.steps still has
to be run through SkillEngine/ActionBroker by the caller, subject to the
same authority/policy checks as any other submission.
"""
from __future__ import annotations

import json
import re

from ..capabilities import Capability, CapabilityRegistry
from ..providers import ModelRouter
from .models import CapabilityGap, PlanResult, PlannedStep

_ARRAY_PATTERN = re.compile(r"\[.*\]", re.DOTALL)


def _extract_json_array(raw: str) -> list | None:
    match = _ARRAY_PATTERN.search(raw)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, list) else None


def _build_prompt(objective: str, capabilities: list[Capability]) -> str:
    catalog_lines = "\n".join(f"- {c.name} ({c.domain}): {c.description}" for c in capabilities)
    return (
        "You are planning concrete steps for AURA, an autonomous operating system. "
        "You may ONLY use capabilities from this exact list -- never invent a name:\n"
        f"{catalog_lines}\n\n"
        f"Objective: {objective}\n\n"
        "Respond with ONLY a JSON array. Each element is either:\n"
        '  {"capability_name": "<one of the names above>", "params": {...}, "reasoning": "..."}\n'
        "or, if no listed capability covers part of the objective:\n"
        '  {"missing_capability": "<what is needed>", "required_tool": "...", "required_provider": "...", '
        '"required_permission": "...", "next_action": "..."}\n'
        "Return an empty array [] if nothing here is relevant to the objective."
    )


def parse_plan_response(objective: str, raw: str, available_capabilities: list[Capability]) -> PlanResult:
    """Pure and independently testable, exactly like parse_plan(): given
    the model's raw text and the real available-capability list, decide
    what's genuinely executable versus what's a gap. Never guesses."""
    known_names = {c.name for c in available_capabilities}
    result = PlanResult(
        objective=objective, available_capabilities=sorted(known_names), raw_response=raw,
    )

    items = _extract_json_array(raw)
    if items is None:
        result.gaps.append(CapabilityGap(
            objective=objective, missing_capability="could not parse a plan from the model's response",
            next_action="rephrase the request or supply more detail",
        ))
        return result

    for item in items:
        if not isinstance(item, dict):
            continue

        capability_name = item.get("capability_name")
        if isinstance(capability_name, str) and capability_name in known_names:
            result.steps.append(PlannedStep(
                capability_name=capability_name,
                params=item.get("params") if isinstance(item.get("params"), dict) else {},
                reasoning=str(item.get("reasoning", "")),
            ))
            continue

        if isinstance(capability_name, str) and capability_name not in known_names:
            # The model named something that doesn't exist or isn't
            # currently available -- report it as a gap, never execute
            # a hallucinated capability.
            result.gaps.append(CapabilityGap(
                objective=objective,
                missing_capability=f"model proposed unknown capability '{capability_name}'",
                next_action="verify the capability name or build/register it before retrying",
            ))
            continue

        missing = item.get("missing_capability")
        if isinstance(missing, str) and missing:
            result.gaps.append(CapabilityGap(
                objective=objective,
                missing_capability=missing,
                required_tool=str(item.get("required_tool", "")),
                required_provider=str(item.get("required_provider", "")),
                required_permission=str(item.get("required_permission", "")),
                next_action=str(item.get("next_action", "")),
            ))

    return result


class UniversalPlanner:
    def __init__(self, model_router: ModelRouter, capabilities: CapabilityRegistry) -> None:
        self._model_router = model_router
        self._capabilities = capabilities

    async def plan(self, objective: str) -> PlanResult:
        available = self._capabilities.list_available()
        prompt = _build_prompt(objective, available)
        chunks = [chunk async for chunk in self._model_router.generate_stream(prompt, history=[])]
        raw = "".join(chunks)
        return parse_plan_response(objective, raw, available)
