"""Built-in deterministic actions."""
from __future__ import annotations

from ..memory import MemoryStore
from ..status import CapabilityStatus, registry
from .registry import ActionRegistry, ActionResult


def build_default_registry(memory: MemoryStore) -> ActionRegistry:
    reg = ActionRegistry()

    def handle_status(_text: str) -> ActionResult:
        snapshot = registry.snapshot()
        lines = [f"{name}: {info['status']}" for name, info in snapshot.items()]
        return ActionResult(handled=True, status=CapabilityStatus.LIVE, message="\n".join(lines))

    def handle_help(_text: str) -> ActionResult:
        triggers = ", ".join(reg.known_triggers())
        return ActionResult(handled=True, status=CapabilityStatus.LIVE, message=f"Known instant commands: {triggers}")

    def handle_show_tasks(_text: str) -> ActionResult:
        commitments = memory.open_commitments()
        if not commitments:
            return ActionResult(handled=True, status=CapabilityStatus.LIVE, message="No open commitments.")
        lines = [f"- {c.description} (due: {c.due_at or 'no deadline'})" for c in commitments]
        return ActionResult(handled=True, status=CapabilityStatus.LIVE, message="\n".join(lines))

    def handle_open_chrome(_text: str) -> ActionResult:
        record = registry.get("computer_control.desktop")
        return ActionResult(
            handled=True,
            status=CapabilityStatus.NOT_CONNECTED,
            message=f"Cannot open applications: {record.detail if record else 'computer control not implemented'}",
        )

    def handle_mute(_text: str) -> ActionResult:
        record = registry.get("computer_control.desktop")
        return ActionResult(
            handled=True,
            status=CapabilityStatus.NOT_CONNECTED,
            message=f"Cannot control system audio: {record.detail if record else 'computer control not implemented'}",
        )

    reg.register("status", handle_status)
    reg.register("show status", handle_status)
    reg.register("help", handle_help)
    reg.register("show tasks", handle_show_tasks)
    reg.register("show commitments", handle_show_tasks)
    reg.register("open chrome", handle_open_chrome)
    reg.register("mute", handle_mute)

    return reg
