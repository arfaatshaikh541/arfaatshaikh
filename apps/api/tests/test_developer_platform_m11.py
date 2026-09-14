import hashlib
import hmac

import app.models  # noqa: F401
from app.db.base import Base
from app.services.developer_platform import CredentialPolicyInput, evaluate_credential_policy, evaluate_delivery_retry, validate_webhook_endpoint, verify_webhook_signature


def test_developer_platform_tables_registered():
    expected = {"developer_applications", "api_client_credentials", "api_client_scopes", "webhook_subscriptions", "webhook_deliveries"}
    assert expected.issubset(Base.metadata.tables)


def test_credential_policy_accepts_scoped_hashed_key():
    result = evaluate_credential_policy(CredentialPolicyInput("woi_live_ab12", "a" * 64, {"quran.read", "knowledge.read"}, 120, "active"))
    assert result["credential_ready"] is True


def test_credential_policy_rejects_unknown_scope_and_plain_secret():
    result = evaluate_credential_policy(CredentialPolicyInput("bad", "plaintext", {"admin.everything"}, 120, "active"))
    assert result["credential_ready"] is False
    assert any(code.startswith("unsupported_scopes:") for code in result["reason_codes"])
    assert "hashed_secret_required" in result["reason_codes"]


def test_suspended_application_cannot_receive_credential():
    result = evaluate_credential_policy(CredentialPolicyInput("woi_live_ab12", "b" * 64, {"quran.read"}, 60, "suspended"))
    assert "application_not_active" in result["reason_codes"]


def test_webhook_endpoint_blocks_private_networks_and_http():
    result = validate_webhook_endpoint("http://127.0.0.1/hook", {"source.published"})
    assert result["valid"] is False
    assert "https_endpoint_required" in result["reason_codes"]
    assert "non_public_ip_forbidden" in result["reason_codes"]


def test_webhook_endpoint_accepts_governed_https_event():
    result = validate_webhook_endpoint("https://integrator.example/webhooks/world-of-islam", {"source.corrected"})
    assert result["valid"] is True


def test_webhook_signature_is_deterministic_and_tamper_evident():
    payload = b'{"event":"source.published"}'
    timestamp = "1785010000"
    secret = "a-strong-integration-secret"
    signature = hmac.new(secret.encode(), timestamp.encode() + b"." + payload, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(payload=payload, timestamp=timestamp, signature_hex=signature, secret=secret)["verified"] is True
    assert verify_webhook_signature(payload=payload + b"x", timestamp=timestamp, signature_hex=signature, secret=secret)["verified"] is False


def test_delivery_retry_policy_retries_only_transient_failures():
    assert evaluate_delivery_retry(status_code=503, attempt_count=2)["action"] == "retry"
    assert evaluate_delivery_retry(status_code=400, attempt_count=2)["action"] == "discard"
    assert evaluate_delivery_retry(status_code=204, attempt_count=1)["action"] == "delivered"
    assert evaluate_delivery_retry(status_code=503, attempt_count=12)["action"] == "discard"
