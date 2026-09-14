from __future__ import annotations

import hashlib
import hmac
import ipaddress
from dataclasses import dataclass
from urllib.parse import urlparse

DEVELOPER_PLATFORM_POLICY_VERSION = "developer-platform-v1"
ALLOWED_SCOPES = {
    "quran.read",
    "hadith.read",
    "tafsir.read",
    "knowledge.read",
    "learning.read",
    "research.read",
    "assistant.request",
    "webhooks.manage",
}
ALLOWED_WEBHOOK_EVENTS = {
    "source.published",
    "source.corrected",
    "course.published",
    "research.updated",
    "scholarly.review.completed",
}


@dataclass(frozen=True)
class CredentialPolicyInput:
    key_prefix: str
    secret_hash: str
    scopes: set[str]
    rate_limit_per_minute: int
    application_status: str


def _valid_hex_digest(value: str, lengths: set[int] = {64, 128}) -> bool:
    return len(value) in lengths and all(character in "0123456789abcdefABCDEF" for character in value)


def evaluate_credential_policy(value: CredentialPolicyInput) -> dict[str, object]:
    reasons: list[str] = []
    if value.application_status != "active":
        reasons.append("application_not_active")
    if not value.key_prefix.startswith("woi_") or not 8 <= len(value.key_prefix) <= 20:
        reasons.append("invalid_key_prefix")
    if not _valid_hex_digest(value.secret_hash):
        reasons.append("hashed_secret_required")
    unsupported = sorted(value.scopes - ALLOWED_SCOPES)
    if unsupported:
        reasons.append("unsupported_scopes:" + ",".join(unsupported))
    if not value.scopes:
        reasons.append("at_least_one_scope_required")
    if not 1 <= value.rate_limit_per_minute <= 6000:
        reasons.append("rate_limit_out_of_bounds")
    return {
        "credential_ready": not reasons,
        "reason_codes": reasons or ["credential_policy_passed"],
        "allowed_scopes": sorted(ALLOWED_SCOPES),
        "policy_version": DEVELOPER_PLATFORM_POLICY_VERSION,
    }


def validate_webhook_endpoint(endpoint_url: str, subscribed_events: set[str]) -> dict[str, object]:
    reasons: list[str] = []
    parsed = urlparse(endpoint_url)
    if parsed.scheme != "https":
        reasons.append("https_endpoint_required")
    if not parsed.hostname:
        reasons.append("hostname_required")
    if parsed.username or parsed.password:
        reasons.append("embedded_credentials_forbidden")
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local"):
        reasons.append("local_endpoint_forbidden")
    try:
        address = ipaddress.ip_address(hostname)
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast:
            reasons.append("non_public_ip_forbidden")
    except ValueError:
        pass
    unsupported = sorted(subscribed_events - ALLOWED_WEBHOOK_EVENTS)
    if unsupported:
        reasons.append("unsupported_webhook_events:" + ",".join(unsupported))
    if not subscribed_events:
        reasons.append("at_least_one_webhook_event_required")
    return {
        "valid": not reasons,
        "reason_codes": reasons or ["webhook_endpoint_valid"],
        "allowed_events": sorted(ALLOWED_WEBHOOK_EVENTS),
        "policy_version": DEVELOPER_PLATFORM_POLICY_VERSION,
    }


def verify_webhook_signature(*, payload: bytes, timestamp: str, signature_hex: str, secret: str) -> dict[str, object]:
    reasons: list[str] = []
    if not timestamp.isdigit():
        reasons.append("invalid_timestamp")
    if not _valid_hex_digest(signature_hex, {64}):
        reasons.append("invalid_signature_format")
    expected = hmac.new(secret.encode("utf-8"), timestamp.encode("ascii", errors="ignore") + b"." + payload, hashlib.sha256).hexdigest()
    if not reasons and not hmac.compare_digest(expected, signature_hex.lower()):
        reasons.append("signature_mismatch")
    return {
        "verified": not reasons,
        "reason_codes": reasons or ["webhook_signature_verified"],
        "policy_version": DEVELOPER_PLATFORM_POLICY_VERSION,
    }


def evaluate_delivery_retry(*, status_code: int | None, attempt_count: int) -> dict[str, object]:
    if attempt_count < 0 or attempt_count > 12:
        raise ValueError("attempt_count must be between 0 and 12")
    retryable = status_code is None or status_code == 429 or 500 <= status_code <= 599
    exhausted = attempt_count >= 12
    if 200 <= (status_code or 0) <= 299:
        action = "delivered"
    elif retryable and not exhausted:
        action = "retry"
    else:
        action = "discard"
    return {
        "action": action,
        "retryable": retryable and not exhausted,
        "attempt_count": attempt_count,
        "policy_version": DEVELOPER_PLATFORM_POLICY_VERSION,
    }
