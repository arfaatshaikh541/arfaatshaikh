"""Generic outbound HTTP connector, gated by a destination allowlist —
per docs/security/README.md#network-security, an agent must not reach an
arbitrary destination just because a request asked it to."""
from __future__ import annotations

from urllib.parse import urlparse

import httpx

from ..governance.action_broker import ActionRequest, HandlerResult
from ..status import CapabilityStatus
from .base import Connector, ConnectorManifest


class HttpConnector(Connector):
    def __init__(self, allowed_hosts: list[str], timeout_seconds: float = 10.0) -> None:
        self._allowed_hosts = set(allowed_hosts)
        self._timeout = timeout_seconds
        self.manifest = ConnectorManifest(
            name="http",
            auth_method="none",
            capabilities=["http.get", "http.post"],
            notes=f"allowed hosts: {sorted(self._allowed_hosts)}",
        )

    def _check_allowed(self, url: str) -> str | None:
        host = urlparse(url).hostname
        if host not in self._allowed_hosts:
            return f"'{host}' is not on the egress allowlist {sorted(self._allowed_hosts)}"
        return None

    def health_check(self) -> HandlerResult:
        if not self._allowed_hosts:
            return HandlerResult(CapabilityStatus.BLOCKED_BY_POLICY, "no hosts on the egress allowlist yet")
        return HandlerResult(CapabilityStatus.LIVE, f"{len(self._allowed_hosts)} host(s) allowlisted")

    def get(self, request: ActionRequest) -> HandlerResult:
        url = request.params["url"]
        denial = self._check_allowed(url)
        if denial:
            return HandlerResult(CapabilityStatus.BLOCKED_BY_POLICY, denial)
        try:
            response = httpx.get(url, timeout=self._timeout)
            return HandlerResult(CapabilityStatus.LIVE, f"{response.status_code}: {response.text[:2000]}")
        except httpx.HTTPError as exc:
            return HandlerResult(CapabilityStatus.DEGRADED, f"request failed: {exc}")

    def post(self, request: ActionRequest) -> HandlerResult:
        url = request.params["url"]
        denial = self._check_allowed(url)
        if denial:
            return HandlerResult(CapabilityStatus.BLOCKED_BY_POLICY, denial)
        try:
            response = httpx.post(url, json=request.params.get("body", {}), timeout=self._timeout)
            return HandlerResult(CapabilityStatus.LIVE, f"{response.status_code}: {response.text[:2000]}")
        except httpx.HTTPError as exc:
            return HandlerResult(CapabilityStatus.DEGRADED, f"request failed: {exc}")

    def handlers(self) -> dict:
        return {"http.get": self.get, "http.post": self.post}
