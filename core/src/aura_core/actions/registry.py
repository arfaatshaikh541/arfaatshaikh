"""Deterministic instant-action lane (Lane A).

Per the mega-prompt's Lane A requirement: known commands should never wake a
model. This registry matches normalized input text against registered
triggers and dispatches directly — no LLM call, sub-millisecond in
practice for local logic.

Handlers that require a capability this build doesn't have (OS-level
computer control) are registered too, but their handler returns
NOT_CONNECTED honestly rather than being silently omitted — so 'open
chrome' is a known, tracked gap, not an unhandled surprise.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..status import CapabilityStatus


@dataclass
class ActionResult:
    handled: bool
    status: CapabilityStatus
    message: str


ActionHandler = Callable[[str], ActionResult]


class ActionRegistry:
    def __init__(self) -> None:
        self._triggers: dict[str, ActionHandler] = {}

    def register(self, trigger: str, handler: ActionHandler) -> None:
        self._triggers[trigger.lower().strip()] = handler

    def dispatch(self, text: str) -> ActionResult | None:
        normalized = text.lower().strip().rstrip(".!?")
        handler = self._triggers.get(normalized)
        if handler is None:
            return None
        return handler(text)

    def known_triggers(self) -> list[str]:
        return sorted(self._triggers.keys())
