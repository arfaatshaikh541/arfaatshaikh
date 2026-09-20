"""Instagram connector: the real, two-step Graph API media publish flow
this document's Meta/Instagram row explicitly named as not yet built --
a genuinely different shape from every other social connector in this
codebase, so it gets its own Connector subclass rather than a
RestApiConnector capability-map entry (which can only ever express one
request per action_type).

The flow (per Meta's real Instagram Graph API documentation):
  1. POST /{ig_user_id}/media    {image_url, caption} -> {"id": "<creation_id>"}
  2. POST /{ig_user_id}/media_publish {creation_id}    -> {"id": "<media_id>"}
A failure between steps is reported at whichever step actually failed,
never silently retried or partially reported as success.

REQUIRES_OWNER_CREDENTIAL: a real Instagram-linked Page access token.
Until configured, health_check() honestly reports READY_TO_CONNECT.
Getting that token needs a live OAuth consent flow in a real browser
(REQUIRES_OWNER_AUTHORIZATION), and Instagram content publishing
permissions need Meta App Review (REQUIRES_PLATFORM_APPROVAL) --
neither of which this connector can honestly claim to provide.
"""
from __future__ import annotations

import httpx

from ..governance.action_broker import ActionRequest, HandlerResult
from ..status import CapabilityStatus
from .base import Connector, ConnectorManifest


class InstagramConnector(Connector):
    def __init__(self, token: str | None = None, base_url: str = "https://graph.facebook.com/v19.0") -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self.manifest = ConnectorManifest(
            name="instagram",
            auth_method="api_key",
            required_credentials=["access_token"],
            capabilities=["instagram.publish_post"],
            notes=self._base_url,
        )

    def _headers(self) -> dict[str, str]:
        if not self._token:
            return {}
        value = self._token if self._token.lower().startswith("bearer ") else f"Bearer {self._token}"
        return {"Authorization": value}

    def health_check(self) -> HandlerResult:
        if not self._token:
            return HandlerResult(CapabilityStatus.READY_TO_CONNECT, "no access token configured yet")
        try:
            response = httpx.get(f"{self._base_url}/me", headers=self._headers(), timeout=10)
            if response.status_code < 500:
                return HandlerResult(CapabilityStatus.LIVE, f"{self._base_url} responded {response.status_code}")
            return HandlerResult(CapabilityStatus.DEGRADED, f"{self._base_url} responded {response.status_code}")
        except httpx.HTTPError as exc:
            return HandlerResult(CapabilityStatus.UNAVAILABLE, f"cannot reach {self._base_url}: {exc}")

    def publish_post(self, request: ActionRequest) -> HandlerResult:
        ig_user_id = request.params["ig_user_id"]
        image_url = request.params["image_url"]
        caption = request.params.get("caption", "")

        try:
            create_response = httpx.post(
                f"{self._base_url}/{ig_user_id}/media",
                headers=self._headers(), json={"image_url": image_url, "caption": caption}, timeout=15,
            )
        except httpx.HTTPError as exc:
            return HandlerResult(CapabilityStatus.DEGRADED, f"media container request failed: {exc}")

        if create_response.status_code >= 400:
            return HandlerResult(
                CapabilityStatus.DEGRADED,
                f"media container creation failed: {create_response.status_code}: {create_response.text[:500]}",
            )
        creation_id = create_response.json().get("id")
        if not creation_id:
            return HandlerResult(CapabilityStatus.DEGRADED, f"media container response had no 'id': {create_response.text[:500]}")

        try:
            publish_response = httpx.post(
                f"{self._base_url}/{ig_user_id}/media_publish",
                headers=self._headers(), json={"creation_id": creation_id}, timeout=15,
            )
        except httpx.HTTPError as exc:
            return HandlerResult(CapabilityStatus.DEGRADED, f"media_publish request failed (container {creation_id} was created): {exc}")

        if publish_response.status_code >= 400:
            return HandlerResult(
                CapabilityStatus.DEGRADED,
                f"media_publish failed (container {creation_id} was created): "
                f"{publish_response.status_code}: {publish_response.text[:500]}",
            )
        return HandlerResult(CapabilityStatus.LIVE, publish_response.text[:2000])

    def handlers(self) -> dict:
        return {"instagram.publish_post": self.publish_post}
