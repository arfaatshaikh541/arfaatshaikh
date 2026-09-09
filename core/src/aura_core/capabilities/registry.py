"""CapabilityRegistry: the single place that answers "what can AURA
actually do right now" by joining three things that already exist and
are each independently real -- the static Capability catalog (metadata),
the ConnectorRegistry (which handlers are actually registered with the
Action Broker in this running process), and the RiskEngine (the
governance tier every submission through the Action Broker is already
classified against). This registry does not gate or execute anything
itself -- every real execution still goes through the Action Broker
exactly as before; this only makes what's available and its real risk
tier introspectable in one place instead of scattered across source
files.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..connectors.registry import ConnectorRegistry
from ..governance.risk_engine import ActionRequest, RiskEngine, RiskTier
from .catalog import CAPABILITY_CATALOG
from .models import Capability


@dataclass
class CapabilityStatusReport:
    capability: Capability
    handler_registered: bool
    risk_tier: RiskTier


class CapabilityRegistry:
    def __init__(self, connectors: ConnectorRegistry, risk_engine: RiskEngine | None = None) -> None:
        self._connectors = connectors
        self._risk = risk_engine or RiskEngine()
        self._catalog = dict(CAPABILITY_CATALOG)

    def register(self, capability: Capability) -> None:
        """Adds (or overrides) one catalog entry -- used by the Dynamic
        Skill Builder path and by tests, never required for the
        built-in catalog itself."""
        self._catalog[capability.name] = capability

    def get(self, name: str) -> Capability | None:
        return self._catalog.get(name)

    def list_all(self) -> list[Capability]:
        return sorted(self._catalog.values(), key=lambda c: c.name)

    def list_by_domain(self, domain: str) -> list[Capability]:
        return [c for c in self.list_all() if c.domain == domain]

    def domains(self) -> list[str]:
        return sorted({c.domain for c in self._catalog.values()})

    def is_handler_registered(self, name: str) -> bool:
        """Whether some connector in THIS running registry actually
        registered a handler for this action_type -- a capability can be
        cataloged (the code exists) without being reachable right now
        (e.g. the connector needing configuration wasn't registered)."""
        return any(name in manifest.capabilities for manifest in self._connectors.manifests())

    def status(self, name: str) -> CapabilityStatusReport | None:
        capability = self.get(name)
        if capability is None:
            return None
        risk = self._risk.classify(ActionRequest(action_type=name))
        return CapabilityStatusReport(
            capability=capability,
            handler_registered=self.is_handler_registered(name),
            risk_tier=risk.tier,
        )

    def list_available(self) -> list[Capability]:
        """Only capabilities whose handler is actually registered right
        now -- what a planner should actually consider using, as opposed
        to what merely exists in the codebase."""
        return [c for c in self.list_all() if self.is_handler_registered(c.name)]
