"""Generic REST API connector — the base pattern for CRM and social
integrations (HubSpot, Instagram Graph API, LinkedIn, etc.). Real HTTP
code, genuinely testable against any REST API including a local fake one
(see tests). A real vendor integration is a matter of supplying its
base_url/api_key/capability_map — the credentials themselves are
REQUIRES_USER_CREDENTIAL, but the connector code is not a stub.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from ..governance.action_broker import ActionRequest, HandlerResult
from ..status import CapabilityStatus
from .base import Connector, ConnectorManifest


@dataclass
class RestCapability:
    method: str  # "GET" | "POST" | "PUT" | "DELETE"
    path_template: str  # e.g. "/contacts/{contact_id}" -- filled from request.params


class RestApiConnector(Connector):
    def __init__(
        self, name: str, base_url: str, capability_map: dict[str, RestCapability], *,
        api_key: str | None = None, header_name: str = "Authorization",
        health_path: str = "/", auth_method: str = "api_key",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._capability_map = capability_map
        self._api_key = api_key
        self._header_name = header_name
        self._health_path = health_path
        # Whether this connector *requires* a credential is a property of
        # the connector type (auth_method), independent of whether one has
        # been configured yet -- conflating the two previously meant
        # health_check's "no key configured" branch could never fire,
        # since the manifest silently downgraded to auth_method="none"
        # the moment api_key was omitted. Caught by test.
        self._requires_credential = auth_method != "none"
        self.manifest = ConnectorManifest(
            name=name,
            auth_method=auth_method,
            required_credentials=["api_key"] if self._requires_credential else [],
            capabilities=list(capability_map.keys()),
            notes=f"{base_url}",
        )

    def _headers(self) -> dict[str, str]:
        if self._api_key is None:
            return {}
        value = self._api_key if self._header_name == "Authorization" and self._api_key.lower().startswith("bearer ") \
            else (f"Bearer {self._api_key}" if self._header_name == "Authorization" else self._api_key)
        return {self._header_name: value}

    def health_check(self) -> HandlerResult:
        if self._requires_credential and not self._api_key:
            return HandlerResult(CapabilityStatus.READY_TO_CONNECT, "no API key configured yet")
        try:
            response = httpx.get(f"{self._base_url}{self._health_path}", headers=self._headers(), timeout=10)
            if response.status_code < 500:
                return HandlerResult(CapabilityStatus.LIVE, f"{self._base_url} responded {response.status_code}")
            return HandlerResult(CapabilityStatus.DEGRADED, f"{self._base_url} responded {response.status_code}")
        except httpx.HTTPError as exc:
            return HandlerResult(CapabilityStatus.UNAVAILABLE, f"cannot reach {self._base_url}: {exc}")

    def _make_handler(self, action_type: str, capability: RestCapability):
        def handle(request: ActionRequest) -> HandlerResult:
            try:
                path = capability.path_template.format(**request.params)
            except KeyError as exc:
                return HandlerResult(CapabilityStatus.DEGRADED, f"missing required param {exc} for {action_type}")

            try:
                response = httpx.request(
                    capability.method, f"{self._base_url}{path}",
                    headers=self._headers(), json=request.params.get("body"), timeout=15,
                )
                if response.status_code < 400:
                    return HandlerResult(CapabilityStatus.LIVE, response.text[:2000])
                return HandlerResult(CapabilityStatus.DEGRADED, f"{response.status_code}: {response.text[:500]}")
            except httpx.HTTPError as exc:
                return HandlerResult(CapabilityStatus.DEGRADED, f"request failed: {exc}")

        return handle

    def handlers(self) -> dict:
        return {
            action_type: self._make_handler(action_type, capability)
            for action_type, capability in self._capability_map.items()
        }
