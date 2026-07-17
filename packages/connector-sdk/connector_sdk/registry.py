"""Connector registry: maps a connector_id string (as stored on
Campaign.source_key) to a connector instance. Milestone 3 registers the
Google Places connector here alongside the mock one; campaign
orchestration code looks connectors up by id and never imports a
specific connector class directly."""

from connector_sdk.base import BaseConnector
from connector_sdk.mock import MockConnector

_REGISTRY: dict[str, BaseConnector] = {
    "mock": MockConnector(),
}


def get_connector(connector_id: str) -> BaseConnector:
    try:
        return _REGISTRY[connector_id]
    except KeyError:
        raise ValueError(f"Unknown connector_id: {connector_id!r}") from None


def available_connector_ids() -> list[str]:
    return list(_REGISTRY.keys())
