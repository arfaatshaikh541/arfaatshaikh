import app.models  # noqa: F401
from app.db.base import Base
from app.services.developer_access import AccessRequest, evaluate_api_access, evaluate_quota, validate_audit_evidence, validate_usage_record


def test_developer_access_tables_registered():
    expected = {"api_access_decisions", "api_usage_records", "api_quota_windows", "developer_audit_events"}
    assert expected.issubset(Base.metadata.tables)


def test_access_allows_active_scoped_same_tenant_request():
    result = evaluate_api_access(AccessRequest("active", "active", {"quran.read"}, "quran.read", True, False, 4))
    assert result["allowed"] is True


def test_access_denies_cross_tenant_and_missing_scope():
    result = evaluate_api_access(AccessRequest("active", "active", {"hadith.read"}, "quran.read", False, False, 3))
    assert result["allowed"] is False
    assert "tenant_mismatch" in result["reason_codes"]
    assert "required_scope_missing" in result["reason_codes"]


def test_access_returns_429_for_quota_only_failure():
    result = evaluate_api_access(AccessRequest("active", "active", {"quran.read"}, "quran.read", True, False, 0))
    assert result["response_status_code"] == 429


def test_quota_is_fail_closed_at_limit():
    assert evaluate_quota(current_count=9, limit_count=10)["allowed"] is True
    assert evaluate_quota(current_count=10, limit_count=10)["allowed"] is False


def test_usage_record_requires_canonical_route_and_idempotency():
    good = validate_usage_record(idempotency_key="idem-123456789", request_id="req-12345678", route_template="/v1/quran/{ayah}", billable_units=1)
    bad = validate_usage_record(idempotency_key="short", request_id="x", route_template="quran?x=1", billable_units=1)
    assert good["valid"] is True
    assert bad["valid"] is False


def test_usage_fingerprint_is_deterministic():
    a = validate_usage_record(idempotency_key="idem-123456789", request_id="req-12345678", route_template="/v1/quran", billable_units=1)
    b = validate_usage_record(idempotency_key="idem-123456789", request_id="req-12345678", route_template="/v1/quran", billable_units=1)
    assert a["fingerprint"] == b["fingerprint"]


def test_audit_event_requires_real_fingerprint_and_known_event():
    assert validate_audit_evidence(evidence_sha256="a" * 64, event_type="credential.used", summary="Credential used for governed API request")["valid"] is True
    assert validate_audit_evidence(evidence_sha256="plain", event_type="unknown", summary="x")["valid"] is False
