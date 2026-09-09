"""WhatsApp Business connector: real Cloud API integration.

Extended in this pass to close the gap FINAL_COMPLETION_AUDIT.md called
out: "Message templates (required for the first message in a 24-hour
window) and media messages are not built, only text." Templates and
media messages get their own dedicated action_types
(whatsapp.send_template_message, whatsapp.send_media_message) rather than
just documenting "whatsapp.send_message accepts any body you construct",
because this codebase's risk/policy configuration and observation
extractors (executive/observation.py) are both keyed by action_type -- an
opaque passthrough body means autonomy policy and the World Model can
never distinguish "sent a template" from "sent a media file" from "sent
free text". Each new action_type builds its own valid Cloud API request
body from named params instead of asking the caller to hand-construct raw
Graph API JSON, matching this session's "explicit, narrow, never a
generic guesser" rule for anything that writes into governed state.

This is now a dedicated Connector subclass rather than a RestApiConnector
capability-map configuration, since building a template/media body needs
per-action_type logic that a single-request-per-action_type capability
map cannot express (the same reason InstagramConnector and ImapConnector
are dedicated subclasses rather than RestApiConnector configurations).

REQUIRES_OWNER_CREDENTIAL: a real WhatsApp Business Cloud API access
token and phone_number_id. Until configured, health_check() honestly
reports READY_TO_CONNECT. A real WhatsApp Business phone number, its Meta
Business verification, and pre-approved template definitions are
REQUIRES_EXTERNAL_PROVIDER + REQUIRES_OWNER_CREDENTIAL -- this connector
provides the governed, tested Action-Broker pipeline for using them once
the owner has both, not the account or the templates themselves.
"""
from __future__ import annotations

import httpx

from ..governance.action_broker import ActionRequest, HandlerResult
from ..status import CapabilityStatus
from .base import Connector, ConnectorManifest


class WhatsAppConnector(Connector):
    def __init__(self, token: str | None = None, base_url: str = "https://graph.facebook.com/v19.0") -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self.manifest = ConnectorManifest(
            name="whatsapp",
            auth_method="api_key",
            required_credentials=["access_token"],
            capabilities=[
                "whatsapp.send_message",
                "whatsapp.get_phone_number_status",
                "whatsapp.send_template_message",
                "whatsapp.send_media_message",
            ],
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
            response = httpx.get(f"{self._base_url}/", headers=self._headers(), timeout=10)
            if response.status_code < 500:
                return HandlerResult(CapabilityStatus.LIVE, f"{self._base_url} responded {response.status_code}")
            return HandlerResult(CapabilityStatus.DEGRADED, f"{self._base_url} responded {response.status_code}")
        except httpx.HTTPError as exc:
            return HandlerResult(CapabilityStatus.UNAVAILABLE, f"cannot reach {self._base_url}: {exc}")

    def _post_message(self, phone_number_id: str, body: dict | None) -> HandlerResult:
        try:
            response = httpx.post(
                f"{self._base_url}/{phone_number_id}/messages",
                headers=self._headers(), json=body, timeout=15,
            )
        except httpx.HTTPError as exc:
            return HandlerResult(CapabilityStatus.DEGRADED, f"request failed: {exc}")
        if response.status_code >= 400:
            return HandlerResult(CapabilityStatus.DEGRADED, f"{response.status_code}: {response.text[:500]}")
        return HandlerResult(CapabilityStatus.LIVE, response.text[:2000])

    def send_message(self, request: ActionRequest) -> HandlerResult:
        phone_number_id = request.params["phone_number_id"]
        return self._post_message(phone_number_id, request.params.get("body"))

    def get_phone_number_status(self, request: ActionRequest) -> HandlerResult:
        phone_number_id = request.params["phone_number_id"]
        try:
            response = httpx.get(f"{self._base_url}/{phone_number_id}", headers=self._headers(), timeout=15)
        except httpx.HTTPError as exc:
            return HandlerResult(CapabilityStatus.DEGRADED, f"request failed: {exc}")
        if response.status_code >= 400:
            return HandlerResult(CapabilityStatus.DEGRADED, f"{response.status_code}: {response.text[:500]}")
        return HandlerResult(CapabilityStatus.LIVE, response.text[:2000])

    def send_template_message(self, request: ActionRequest) -> HandlerResult:
        """Templates are required by the Cloud API to open (or re-open) a
        24-hour customer service window -- a plain text message cannot do
        this. `components` follows the Cloud API's own template-component
        shape (header/body/button parameters); passed through verbatim
        since its shape is defined per-template by whatever the owner had
        pre-approved in Meta Business Manager, not something this
        connector can usefully second-guess or validate."""
        phone_number_id = request.params["phone_number_id"]
        to = request.params["to"]
        template_name = request.params["template_name"]
        language_code = request.params.get("language_code", "en_US")
        components = request.params.get("components")

        template: dict = {"name": template_name, "language": {"code": language_code}}
        if components is not None:
            template["components"] = components

        body = {"messaging_product": "whatsapp", "to": to, "type": "template", "template": template}
        return self._post_message(phone_number_id, body)

    def send_media_message(self, request: ActionRequest) -> HandlerResult:
        """media_type is one of the Cloud API's supported kinds: image,
        video, audio, document, sticker. Exactly one of media_id (an
        already-uploaded Meta media id) or media_link (a public URL) is
        required, per the real Cloud API's own contract -- neither this
        connector nor the broker can supply a default for media the owner
        must actually control."""
        phone_number_id = request.params["phone_number_id"]
        to = request.params["to"]
        media_type = request.params["media_type"]
        media_id = request.params.get("media_id")
        media_link = request.params.get("media_link")
        caption = request.params.get("caption")

        if not media_id and not media_link:
            return HandlerResult(CapabilityStatus.DEGRADED, "send_media_message requires either 'media_id' or 'media_link'")

        media_object: dict = {"id": media_id} if media_id else {"link": media_link}
        if caption is not None:
            media_object["caption"] = caption

        body = {"messaging_product": "whatsapp", "to": to, "type": media_type, media_type: media_object}
        return self._post_message(phone_number_id, body)

    def handlers(self) -> dict:
        return {
            "whatsapp.send_message": self.send_message,
            "whatsapp.get_phone_number_status": self.get_phone_number_status,
            "whatsapp.send_template_message": self.send_template_message,
            "whatsapp.send_media_message": self.send_media_message,
        }


def build_whatsapp_connector(token: str | None = None, base_url: str = "https://graph.facebook.com/v19.0") -> WhatsAppConnector:
    """base_url is overridable so this can be pointed at a real local
    fake server in tests, exactly the way every other connector in this
    project is verified against something real rather than mocked."""
    return WhatsAppConnector(token=token, base_url=base_url)
