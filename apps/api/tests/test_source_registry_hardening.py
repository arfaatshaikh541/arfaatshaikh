from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_retrieval_eligibility_requires_active_policy():
    text = (ROOT / "app/services/source_lifecycle.py").read_text()
    assert "policy_present" in text
    assert "policy_reviewers_met" in text
    assert "policy_domains_met" in text


def test_policy_domains_and_reviewer_count_are_enforced():
    text = (ROOT / "app/services/sources.py").read_text()
    assert "required_domains.issubset(approved_domains)" in text
    assert "len(unique_reviewers) >= policy.minimum_reviewers" in text


def test_reviewer_queue_and_provenance_routes_exist():
    text = (ROOT / "app/api/routes/sources.py").read_text()
    assert '"/reviewer/queue"' in text
    assert '"/admin/claims/{claim_id}/provenance"' in text
    assert '"/admin/audit-exports"' in text


def test_audit_export_is_append_only():
    migration = (ROOT / "alembic/versions/20260725_0008_registry_hardening.py").read_text()
    assert "trg_source_audit_exports_immutable" in migration
    assert "BEFORE UPDATE OR DELETE" in migration


def test_audit_export_has_integrity_digest():
    text = (ROOT / "app/services/source_registry_admin.py").read_text()
    assert "payload_sha256" in text
    assert "sha256(payload).hexdigest()" in text
