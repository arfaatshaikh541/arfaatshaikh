"""ConnectorRegistry: the single place connectors are registered from,
so their handlers reach the Action Broker and their health reaches the
capability status registry through one consistent path.
"""
from __future__ import annotations

from ..governance.action_broker import ActionBroker
from ..status import registry as status_registry
from .base import Connector, ConnectorManifest


class ConnectorRegistry:
    def __init__(self, broker: ActionBroker) -> None:
        self._broker = broker
        self._connectors: dict[str, Connector] = {}

    def register(self, connector: Connector) -> None:
        self._connectors[connector.manifest.name] = connector
        for action_type, handler in connector.handlers().items():
            self._broker.register_handler(action_type, handler)
        self.refresh_status(connector.manifest.name)

    def refresh_status(self, name: str) -> None:
        connector = self._connectors[name]
        result = connector.health_check()
        status_registry.set(f"connector.{name}", result.status, result.message)

    def refresh_all(self) -> None:
        for name in self._connectors:
            self.refresh_status(name)

    def get(self, name: str) -> Connector | None:
        return self._connectors.get(name)

    def manifests(self) -> list[ConnectorManifest]:
        return [c.manifest for c in self._connectors.values()]
