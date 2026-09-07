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
from .connectors import (
    BrowserConnector,
    CloudConnector,
    ConnectorRegistry,
    DesktopControlConnector,
    FilesystemConnector,
    HttpConnector,
    ImapConnector,
    MockCloudProvider,
    MockTelephonyProvider,
    SmtpConnector,
    TelephonyConnector,
    build_github_connector,
    build_linkedin_connector,
    build_meta_connector,
    build_whatsapp_connector,
    InstagramConnector,
)
from .executive import ExecutiveIntelligence, GoalEngine, MandateEngine, OperatingLoopSupervisor, TaskWorker
from .governance import ActionBroker, ApprovalEngine, AuditLog, CredentialBroker, PolicyEngine, RiskEngine
from .guardian import SecurityGuardian
from .identity import EnrollmentEngine
from .memory import MemoryStore, WorldModelStore
from .providers import ModelRouter, OllamaEmbeddingProvider, OllamaProvider
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
    world_model: WorldModelStore
    policy: PolicyEngine
    risk: RiskEngine
    approvals: ApprovalEngine
    credentials: CredentialBroker
    audit: AuditLog
    enrollment: EnrollmentEngine
    broker: ActionBroker
    guardian: SecurityGuardian
    tasks: TaskEngine
    goals: GoalEngine
    mandates: MandateEngine
    executive: ExecutiveIntelligence
    worker: TaskWorker
    operating_loop: OperatingLoopSupervisor
    triggers: TriggerMap
    model_router: ModelRouter
    connectors: ConnectorRegistry


def _seed_default_policies(policy: PolicyEngine) -> None:
    for action_type, (level, notes) in _DEFAULT_AUTONOMY_LEVELS.items():
        if not policy.has_policy(action_type):
            policy.set_autonomy_level(action_type, level, notes=notes)


def build_runtime(settings: Settings | None = None) -> Runtime:
    settings = settings or load_settings()

    memory = MemoryStore(settings.database_url)
    world_model = WorldModelStore(settings.database_url)
    registry.set("memory.store", CapabilityStatus.LIVE, f"connected to {settings.database_url}")

    policy = PolicyEngine(settings.database_url)
    risk = RiskEngine()
    approvals = ApprovalEngine(settings.database_url)
    credentials = CredentialBroker()
    audit = AuditLog(settings.database_url)
    enrollment = EnrollmentEngine(settings.database_url)
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
    fast_ollama = (
        OllamaProvider(host=settings.ollama_host, model=settings.ollama_fast_model)
        if settings.ollama_fast_model else None
    )
    embedding_provider = OllamaEmbeddingProvider(host=settings.ollama_host, model=settings.ollama_embedding_model)
    model_router = ModelRouter(
        primary=ollama, allow_test_fallback=settings.allow_test_provider,
        fast=fast_ollama, embedding=embedding_provider,
    )

    goals = GoalEngine(settings.database_url)
    mandates = MandateEngine(settings.database_url)
    executive = ExecutiveIntelligence(goals, tasks, memory, model_router, broker=broker)
    worker = TaskWorker(tasks, broker, goals, memory, world_model)
    operating_loop = OperatingLoopSupervisor(executive, worker, tasks, mandates, goals)

    connectors = _build_connectors(broker, settings)

    return Runtime(
        settings=settings, memory=memory, world_model=world_model, policy=policy, risk=risk,
        approvals=approvals, credentials=credentials, audit=audit, enrollment=enrollment,
        broker=broker, guardian=guardian, tasks=tasks, goals=goals, mandates=mandates,
        executive=executive, worker=worker, operating_loop=operating_loop,
        triggers=triggers, model_router=model_router, connectors=connectors,
    )


def _build_connectors(broker: ActionBroker, settings: Settings) -> ConnectorRegistry:
    """Registers every connector that can be constructed with what's known
    right now -- no credentials required for filesystem/http/desktop/
    telephony(mock), so those are always registered and health-checked for
    real. Email and browser are registered only when configured, since an
    unconfigured SmtpConnector or a browser with no allowlist would just be
    a handler that always fails -- better to leave the capability
    NOT_CONNECTED with an honest reason than register a handler that can
    never succeed.
    """
    registry_ = ConnectorRegistry(broker)
    registry_.register(FilesystemConnector(settings.filesystem_sandbox_dir))
    registry_.register(HttpConnector(settings.http_allowed_hosts))
    registry_.register(DesktopControlConnector())
    registry_.register(TelephonyConnector(MockTelephonyProvider(), from_number=settings.telephony_from_number))
    registry_.register(CloudConnector(MockCloudProvider()))

    if settings.smtp_host:
        registry_.register(SmtpConnector(
            settings.smtp_host, settings.smtp_port, username=settings.smtp_username,
            password=settings.smtp_password, use_starttls=settings.smtp_use_starttls,
            from_address=settings.smtp_from_address,
        ))
    else:
        registry.set("connector.email", CapabilityStatus.NOT_CONNECTED, "set AURA_SMTP_HOST (and credentials) to enable")

    if settings.imap_host:
        registry_.register(ImapConnector(
            settings.imap_host, settings.imap_port, username=settings.imap_username,
            password=settings.imap_password, use_ssl=settings.imap_use_ssl,
        ))
    else:
        registry.set("connector.email_inbox", CapabilityStatus.NOT_CONNECTED, "set AURA_IMAP_HOST (and credentials) to enable")

    registry_.register(BrowserConnector(
        executable_path=settings.browser_executable_path, allowed_hosts=settings.http_allowed_hosts,
        profile_dir=settings.browser_profile_dir, download_dir=settings.browser_download_dir,
    ))

    # Always registered, like BrowserConnector -- health_check() itself
    # honestly reports READY_TO_CONNECT without a token rather than this
    # code needing to guess whether one is coming later.
    registry_.register(build_github_connector(token=settings.github_token))
    registry_.register(build_meta_connector(token=settings.meta_token))
    registry_.register(build_whatsapp_connector(token=settings.whatsapp_token))
    registry_.register(build_linkedin_connector(token=settings.linkedin_token))
    registry_.register(InstagramConnector(token=settings.instagram_token))

    return registry_
