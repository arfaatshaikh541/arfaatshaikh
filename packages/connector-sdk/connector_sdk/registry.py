"""Connector registry: maps a connector_id string (as stored on
Campaign.source_key) to a connector instance. Campaign orchestration code
looks connectors up by id and never imports a specific connector class
directly.

`GooglePlacesConnector` is constructed eagerly here just like
`MockConnector`, even though it may have no API key configured - its
constructor only reads `GOOGLE_PLACES_API_KEY` from the environment and
never raises; the ConnectorAuthError for a missing/invalid key only
surfaces when the connector is actually invoked (see
`GooglePlacesConnector._require_api_key`), so an unconfigured key never
breaks process startup."""

from connector_sdk.base import BaseConnector
from connector_sdk.google_places import GooglePlacesConnector
from connector_sdk.mock import MockConnector

_REGISTRY: dict[str, BaseConnector] = {
    "mock": MockConnector(),
    "google_places": GooglePlacesConnector(),
}


def get_connector(connector_id: str) -> BaseConnector:
    try:
        return _REGISTRY[connector_id]
    except KeyError:
        raise ValueError(f"Unknown connector_id: {connector_id!r}") from None


def available_connector_ids() -> list[str]:
    return list(_REGISTRY.keys())
