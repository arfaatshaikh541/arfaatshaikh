"""WhatsApp Business connector: a concrete, real vendor configuration of
the generic RestApiConnector against Meta's WhatsApp Cloud API,
closing the "WhatsApp Business" row's code gap named in
FINAL_COMPLETION_AUDIT.md's section G.

REQUIRES_OWNER_CREDENTIAL: a real WhatsApp Business Cloud API access
token and phone_number_id. Until configured, health_check() honestly
reports READY_TO_CONNECT. A real WhatsApp Business phone number and its
Meta Business verification are REQUIRES_EXTERNAL_PROVIDER +
REQUIRES_OWNER_CREDENTIAL -- this connector provides the governed,
tested Action-Broker pipeline for using them once the owner has both,
not the account itself.
"""
from __future__ import annotations

from .rest_connector import RestApiConnector, RestCapability

WHATSAPP_CAPABILITY_MAP: dict[str, RestCapability] = {
    # The Cloud API's send-message endpoint is keyed by the sender's
    # phone_number_id, not a WhatsApp Business Account id. Pass
    # params={"phone_number_id":..., "body": {"messaging_product": "whatsapp", "to": "...", "type": "text", "text": {"body": "..."}}}.
    "whatsapp.send_message": RestCapability("POST", "/{phone_number_id}/messages"),
    "whatsapp.get_phone_number_status": RestCapability("GET", "/{phone_number_id}"),
}


def build_whatsapp_connector(token: str | None = None, base_url: str = "https://graph.facebook.com/v19.0") -> RestApiConnector:
    """base_url is overridable so this can be pointed at a real local
    fake server in tests, exactly the way every other connector in this
    project is verified against something real rather than mocked."""
    return RestApiConnector(
        name="whatsapp", base_url=base_url, capability_map=WHATSAPP_CAPABILITY_MAP,
        api_key=token, header_name="Authorization", health_path="/", auth_method="api_key",
    )
