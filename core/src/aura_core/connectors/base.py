"""Connector framework: the standard interface every external integration
implements, per docs/connectors/README.md. A connector declares what it
needs and what it can do (its manifest), reports honest health, and
registers its capabilities as Action Broker handlers — nothing calls a
connector's methods directly, exactly like the built-in deterministic
actions.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..governance.action_broker import ActionHandler, HandlerResult


@dataclass
class ConnectorManifest:
    name: str
    auth_method: str  # "none" | "api_key" | "oauth2" | "smtp_credentials" | "custom"
    required_credentials: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)  # action_type strings it provides handlers for
    notes: str = ""


class Connector(ABC):
    manifest: ConnectorManifest

    @abstractmethod
    def health_check(self) -> HandlerResult:
        """Must perform a real check (credentials present? reachable?)
        — never assume LIVE from configuration alone."""

    @abstractmethod
    def handlers(self) -> dict[str, ActionHandler]:
        """action_type -> handler, registered with the Action Broker by
        ConnectorRegistry.register(). A connector never registers itself
        directly with a broker — this keeps the registration path
        singular and auditable."""
