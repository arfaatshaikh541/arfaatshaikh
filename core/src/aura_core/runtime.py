"""Runtime assembly: the one place that wires memory, the governance
stack, the model router, and the deterministic triggers together. Both the
CLI and the API build a Runtime from this single function so there is
exactly one definition of "how AURA's components fit together" — not two
copies that can drift apart.
"""
from __future__ import annotations

from dataclasses import dataclass

from .actions import TriggerMap, build_default_handlers, build_default_triggers
from .config import Settings, load_settings
from .governance import ActionBroker, ApprovalEngine, AuditLog, CredentialBroker, PolicyEngine, RiskEngine
from .guardian import SecurityGuardian
from .memory import MemoryStore
from .providers import ModelRouter, OllamaProvider
from .status import CapabilityStatus, registry
from .tasks import TaskEngine

# Seeded once per fresh policy store. Only applied when no explicit policy
# already exists for the action_type, so an owner's later adjustment is
# never silently reverted on the next startup.
_DEFAULT_AUTONOMY_LEVELS: dict[str, tuple[int, str]] = {
    "status.read": (4, "read-only, local, GREEN — default seed"),
    "help.read": (4, "read-only, local, GREEN — default seed"),
    "tasks.read": (4, "read-only, local, GREEN — default seed"),
    "computer_control.open_app": (1, "capability not connected in this build; recommend-only until it is — default seed"),
    "computer_control.system_control": (1, "capability not connected in this build; recommend-only until it is — default seed"),
}


@dataclass
class Runtime:
    settings: Settings
    memory: MemoryStore
    policy: PolicyEngine
    risk: RiskEngine
    approvals: ApprovalEngine
    credentials: CredentialBroker
    audit: AuditLog
    broker: ActionBroker
    guardian: SecurityGuardian
    tasks: TaskEngine
    triggers: TriggerMap
    model_router: ModelRouter


def _seed_default_policies(policy: PolicyEngine) -> None:
    for action_type, (level, notes) in _DEFAULT_AUTONOMY_LEVELS.items():
        if not policy.has_policy(action_type):
            policy.set_autonomy_level(action_type, level, notes=notes)


def build_runtime(settings: Settings | None = None) -> Runtime:
    settings = settings or load_settings()

    memory = MemoryStore(settings.database_url)
    registry.set("memory.store", CapabilityStatus.LIVE, f"connected to {settings.database_url}")

    policy = PolicyEngine(settings.database_url)
    risk = RiskEngine()
    approvals = ApprovalEngine(settings.database_url)
    credentials = CredentialBroker()
    audit = AuditLog(settings.database_url)
    _seed_default_policies(policy)

    guardian = SecurityGuardian(audit, policy, settings.database_url)
    broker = ActionBroker(
        policy, risk, approvals, credentials, audit,
        on_audit=guardian.evaluate,  # Guardian checks every new entry as it's written
    )
    tasks = TaskEngine(settings.database_url)

    triggers = build_default_triggers()
    handlers = build_default_handlers(memory, triggers)
    for action_type, handler in handlers.items():
        broker.register_handler(action_type, handler)

    ollama = OllamaProvider(host=settings.ollama_host, model=settings.ollama_model)
    model_router = ModelRouter(primary=ollama, allow_test_fallback=settings.allow_test_provider)

    return Runtime(
        settings=settings, memory=memory, policy=policy, risk=risk,
        approvals=approvals, credentials=credentials, audit=audit,
        broker=broker, guardian=guardian, tasks=tasks,
        triggers=triggers, model_router=model_router,
    )
