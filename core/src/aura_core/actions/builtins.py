"""Built-in triggers and their Action-Broker handlers.

`build_default_triggers()` maps conversational text to action_types.
`build_default_handlers()` maps those same action_types to the functions
that actually do the work — registered with the Action Broker, never
called directly. Handlers for capabilities this build doesn't have
(OS-level computer control) return NOT_CONNECTED honestly rather than
being omitted, so the gap is tracked, not silently absent.
"""
from __future__ import annotations

from ..governance.action_broker import HandlerResult
from ..governance.risk_engine import ActionRequest
from ..memory import MemoryStore
from ..status import CapabilityStatus, registry
from .registry import TriggerMap


def build_default_triggers() -> TriggerMap:
    triggers = TriggerMap()
    triggers.register("status", "status.read")
    triggers.register("show status", "status.read")
    triggers.register("help", "help.read")
    triggers.register("show tasks", "tasks.read")
    triggers.register("show commitments", "tasks.read")
    triggers.register("open chrome", "computer_control.open_app")
    triggers.register("mute", "computer_control.system_control")
    return triggers


def build_default_handlers(memory: MemoryStore, triggers: TriggerMap) -> dict[str, callable]:
    def handle_status(_request: ActionRequest) -> HandlerResult:
        snapshot = registry.snapshot()
        lines = [f"{name}: {info['status']}" for name, info in snapshot.items()]
        return HandlerResult(status=CapabilityStatus.LIVE, message="\n".join(lines))

    def handle_help(_request: ActionRequest) -> HandlerResult:
        known = ", ".join(triggers.known_triggers())
        return HandlerResult(status=CapabilityStatus.LIVE, message=f"Known instant commands: {known}")

    def handle_show_tasks(_request: ActionRequest) -> HandlerResult:
        commitments = memory.open_commitments()
        if not commitments:
            return HandlerResult(status=CapabilityStatus.LIVE, message="No open commitments.")
        lines = [f"- {c.description} (due: {c.due_at or 'no deadline'})" for c in commitments]
        return HandlerResult(status=CapabilityStatus.LIVE, message="\n".join(lines))

    def handle_open_app(_request: ActionRequest) -> HandlerResult:
        record = registry.get("computer_control.desktop")
        return HandlerResult(
            status=CapabilityStatus.NOT_CONNECTED,
            message=record.detail if record else "computer control not implemented in this build",
        )

    def handle_system_control(_request: ActionRequest) -> HandlerResult:
        record = registry.get("computer_control.desktop")
        return HandlerResult(
            status=CapabilityStatus.NOT_CONNECTED,
            message=record.detail if record else "computer control not implemented in this build",
        )

    return {
        "status.read": handle_status,
        "help.read": handle_help,
        "tasks.read": handle_show_tasks,
        "computer_control.open_app": handle_open_app,
        "computer_control.system_control": handle_system_control,
    }
