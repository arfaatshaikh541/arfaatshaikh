import app.models  # noqa: F401
from app.db.base import Base
from app.services.knowledge_sync_integrity import compare_snapshots, compute_partition_digest, compute_snapshot_root, evaluate_repair_plan, evaluate_snapshot_seal, verify_snapshot_integrity


def test_integrity_tables_registered():
    assert {"knowledge_sync_snapshots", "knowledge_sync_partition_digests", "knowledge_sync_drift_reports", "knowledge_sync_repair_plans", "knowledge_sync_integrity_verifications"}.issubset(Base.metadata.tables)


def test_partition_digest_is_deterministic_and_ordered():
    items = [{"canonical_id": "a", "payload_sha256": "a"*64}, {"canonical_id": "b", "payload_sha256": "b"*64}]
    first = compute_partition_digest(partition_key="quran:1", ordered_items=items)
    second = compute_partition_digest(partition_key="quran:1", ordered_items=items)
    assert first == second and len(first) == 64


def test_partition_digest_rejects_non_deterministic_order():
    items = [{"canonical_id": "b", "payload_sha256": "a"*64}, {"canonical_id": "a", "payload_sha256": "b"*64}]
    try:
        compute_partition_digest(partition_key="quran:1", ordered_items=items)
    except ValueError as exc:
        assert "strictly ordered" in str(exc)
    else:
        raise AssertionError("unordered items must fail")


def test_snapshot_root_is_order_independent_for_partition_input():
    parts = [{"partition_key": "b", "digest_sha256": "b"*64}, {"partition_key": "a", "digest_sha256": "a"*64}]
    first = compute_snapshot_root(content_type="quran", snapshot_version="v1", partition_digests=parts)
    second = compute_snapshot_root(content_type="quran", snapshot_version="v1", partition_digests=list(reversed(parts)))
    assert first == second


def test_snapshot_seal_requires_trusted_node_and_matching_counts():
    good = evaluate_snapshot_seal(node_status="trusted", content_type="hadith", root_sha256="a"*64, item_count=100, partition_count=2, calculated_partition_count=2)
    bad = evaluate_snapshot_seal(node_status="suspended", content_type="hadith", root_sha256="x", item_count=100, partition_count=3, calculated_partition_count=2)
    assert good["allowed"] is True
    assert bad["allowed"] is False


def test_snapshot_comparison_localizes_drift():
    result = compare_snapshots(local_root_sha256="a"*64, remote_root_sha256="b"*64, local_partitions={"p1": "a"*64, "p2": "b"*64}, remote_partitions={"p1": "a"*64, "p2": "c"*64, "p3": "d"*64})
    assert result["status"] == "drift_detected"
    assert result["divergent_partitions"] == ["p2"]
    assert result["missing_local_partitions"] == ["p3"]


def test_sensitive_divergent_repair_needs_scholarly_approval_and_no_auto_replace():
    blocked = evaluate_repair_plan(content_type="quran", strategy="replace_divergent", partition_keys=["p1"], drift_status="drift_detected", scholarly_approved=False, automatic_replacement=True)
    allowed = evaluate_repair_plan(content_type="quran", strategy="replace_divergent", partition_keys=["p1"], drift_status="drift_detected", scholarly_approved=True, automatic_replacement=False)
    assert blocked["allowed"] is False
    assert allowed["allowed"] is True


def test_integrity_verification_fails_on_partial_or_drifted_snapshot():
    failed = verify_snapshot_integrity(expected_root_sha256="a"*64, calculated_root_sha256="a"*64, expected_partitions=5, verified_partitions=4, unresolved_drift=1)
    passed = verify_snapshot_integrity(expected_root_sha256="a"*64, calculated_root_sha256="a"*64, expected_partitions=5, verified_partitions=5, unresolved_drift=0)
    assert failed["outcome"] == "failed"
    assert passed["outcome"] == "passed"
