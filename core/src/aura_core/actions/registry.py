"""Deterministic instant-action lane (Lane A) — trigger resolution only.

This module's job ends at producing an ActionRequest from matched text. It
does not execute anything — execution happens exclusively through the
Action Broker (see aura_core.governance.action_broker), which is the
mandatory gateway for every consequential action, deterministic or
otherwise. Splitting "what did the owner mean" from "is this allowed to
happen" is what makes the broker a real gate rather than decoration.
"""
from __future__ import annotations

from ..governance.risk_engine import ActionRequest


class TriggerMap:
    def __init__(self) -> None:
        self._triggers: dict[str, str] = {}  # normalized text -> action_type

    def register(self, trigger: str, action_type: str) -> None:
        self._triggers[trigger.lower().strip()] = action_type

    def resolve(self, text: str, requested_by: str = "owner") -> ActionRequest | None:
        normalized = text.lower().strip().rstrip(".!?")
        action_type = self._triggers.get(normalized)
        if action_type is None:
            return None
        return ActionRequest(action_type=action_type, params={"raw_text": text}, requested_by=requested_by)

    def known_triggers(self) -> list[str]:
        return sorted(self._triggers.keys())
