import app.models  # noqa: F401
from app.db.base import Base
from app.services.knowledge_sync import compute_audit_event_hash, evaluate_sync_item, evaluate_sync_node, evaluate_trust_policy, resolve_conflict, validate_manifest


def test_sync_tables_registered():
    assert {"knowledge_sync_nodes", "knowledge_sync_trust_policies", "knowledge_sync_runs", "knowledge_sync_items", "knowledge_sync_conflicts", "knowledge_sync_audit_events"}.issubset(Base.metadata.tables)


def test_node_requires_public_https_and_independent_verification():
    good = evaluate_sync_node(slug="trusted-library", base_url="https://sync.example.org", public_key_fingerprint="a"*64, organisation_active=True, independent_verification=True)
    bad = evaluate_sync_node(slug="Bad Node", base_url="http://localhost", public_key_fingerprint="bad", organisation_active=False, independent_verification=False)
    assert good["trusted"] is True
    assert bad["trusted"] is False


def test_sensitive_content_requires_signatures_and_scholarly_approval():
    result = evaluate_trust_policy(node_status="trusted", direction="pull", content_types={"quran", "hadith"}, require_signature=False, require_scholarly_approval=False, max_items_per_run=100)
    assert result["allowed"] is False
    assert "signature_verification_required" in result["reason_codes"]
    assert "scholarly_approval_required" in result["reason_codes"]


def test_manifest_replay_is_rejected():
    result = validate_manifest(manifest_sha256="b"*64, item_count=5, checkpoint="cp-1", request_id="req-1", replayed_request_ids={"req-1"})
    assert result["accepted"] is False
    assert "replay_detected" in result["reason_codes"]


def test_item_acceptance_is_evidence_and_signature_gated():
    good = evaluate_sync_item(content_type="tafsir", payload_sha256="c"*64, signature_valid=True, content_version="v2", scholarly_approved=True)
    bad = evaluate_sync_item(content_type="tafsir", payload_sha256="bad", signature_valid=False, content_version="", scholarly_approved=False)
    assert good["accepted"] is True
    assert bad["accepted"] is False


def test_divergent_payload_is_marked_conflict():
    result = evaluate_sync_item(content_type="research", payload_sha256="d"*64, signature_valid=True, content_version="v4", scholarly_approved=False, local_payload_sha256="e"*64)
    assert result["conflict"] is True
    assert result["accepted"] is False


def test_conflict_never_auto_accepts_divergent_remote_content():
    result = resolve_conflict(local_version="v1", remote_version="v2", local_sha256="f"*64, remote_sha256="1"*64, remote_scholarly_approved=True)
    assert result["resolution"] == "pending"
    assert "manual_conflict_review_required" in result["reason_codes"]


def test_audit_hash_is_deterministic_and_chain_aware():
    kwargs = dict(run_id="run-1", sequence_number=2, event_type="item.accepted", evidence_sha256="2"*64, previous_event_sha256="3"*64, metadata={"external_id": "quran:1:1"})
    first = compute_audit_event_hash(**kwargs)
    second = compute_audit_event_hash(**kwargs)
    assert first == second
    assert len(first) == 64
