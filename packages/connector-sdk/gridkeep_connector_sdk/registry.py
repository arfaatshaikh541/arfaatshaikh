"""Maps `provider_id` -> connector class. The API seeds `IntegrationCatalog`
rows from `REGISTRY.values()`'s `.definition`; the worker resolves a
connector instance from `REGISTRY[provider_id]` when running a sync.

Real (non-simulator) provider connectors register here too as they're
built in later milestones (Microsoft 365 in Milestone 4, etc.) — this is
the single place that ever needs to change to add one."""

from __future__ import annotations

from gridkeep_connector_sdk.base import Connector
from gridkeep_connector_sdk.mocks import ALL_MOCK_CONNECTORS

REGISTRY: dict[str, type[Connector]] = {cls.definition.provider_id: cls for cls in ALL_MOCK_CONNECTORS}


def get_connector_class(provider_id: str) -> type[Connector]:
    try:
        return REGISTRY[provider_id]
    except KeyError as exc:
        raise KeyError(f"No connector registered for provider_id '{provider_id}'.") from exc
