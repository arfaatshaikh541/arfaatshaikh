"""Provider-neutral connector SDK — architecture §12.

Every connector (real or simulated) implements `Connector` and declares a
`ConnectorDefinition` describing its identity, auth method, required
scopes, permission risk, supported data types/actions, sync modes and
webhook support. GRIDKEEP's `modules.integrations` catalog is seeded from
these definitions — a connector's capabilities are data the policy engine
can reason about, never assumed by calling code (architecture ADR-6).

Simulator connectors (see `gridkeep_connector_sdk.mocks`) set
`is_simulator=True` on their definition and must never be exposed to a
production tenant's integration catalogue — see
`modules.integrations.service.list_catalog`, which filters simulators out
whenever `settings.environment == "production"`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar, Literal

AuthMethod = Literal["oauth2", "api_key", "service_account", "none"]
PermissionRisk = Literal["read_only", "limited_write", "privileged"]
SyncMode = Literal["full", "incremental", "webhook"]


@dataclass(frozen=True)
class ActionSpec:
    """A defensive action this connector's provider can execute. Safety
    class is immutable per action (architecture §17) — a playbook can
    never declare a lower class than what the connector registers here."""

    key: str
    name: str
    safety_class: int  # 0-4
    reversible: bool


@dataclass(frozen=True)
class ConnectorDefinition:
    provider_id: str
    name: str
    category: str
    auth_method: AuthMethod
    required_scopes: tuple[str, ...]
    permission_risk: PermissionRisk
    supported_data_types: tuple[str, ...]
    supported_actions: tuple[ActionSpec, ...]
    sync_modes: tuple[SyncMode, ...]
    webhook_support: bool
    is_simulator: bool = False
    description: str = ""


@dataclass(frozen=True)
class RelationshipRecord:
    """A directed edge this record participates in, resolved against
    another record's identifier once both sides have been ingested."""

    relationship_type: str
    target_identifier_type: str
    target_identifier_value: str


@dataclass(frozen=True)
class NormalizedRecord:
    """One entity as seen by a connector, already mapped onto GRIDKEEP's
    canonical fields. `identifier_type`/`identifier_value` is the key the
    asset-graph ingestion service dedups on (architecture §13); `raw` is
    preserved for evidence/audit but never used for matching."""

    record_type: str
    external_id: str
    identifier_type: str
    identifier_value: str
    display_name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    relationships: tuple[RelationshipRecord, ...] = ()


@dataclass(frozen=True)
class HealthCheckResult:
    healthy: bool
    message: str
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class Connector(ABC):
    """Base class for every connector, real or simulated. Instantiated
    per-sync with the already-decrypted credential (never persisted by
    the connector itself — that's the credential vault's job)."""

    definition: ClassVar[ConnectorDefinition]

    def __init__(self, *, credential_plaintext: str | None, config: dict[str, Any] | None = None) -> None:
        self.credential_plaintext = credential_plaintext
        self.config = config or {}

    @abstractmethod
    async def authenticate(self) -> bool:
        """Validates the credential against the provider. Returns True on
        success; raises ConnectorAuthError on failure."""

    @abstractmethod
    async def health_check(self) -> HealthCheckResult: ...

    @abstractmethod
    def sync(self, *, mode: SyncMode = "full") -> AsyncIterator[NormalizedRecord]:
        """Yields every record visible to this credential for the given
        sync mode. Implementations are async generators."""

    async def disconnect(self) -> None:
        """Default no-op — override for providers that need explicit
        session teardown or token revocation on disconnect."""
        return None


class ConnectorAuthError(Exception):
    pass
