import app.models  # noqa: F401
from app.db.base import Base
from app.services.knowledge_sync_transport import compute_chunk_idempotency_key, evaluate_checkpoint_advance, evaluate_chunk, evaluate_schedule, evaluate_transfer_retry, plan_transfer_chunks, reconcile_batch


def test_transport_tables_registered():
    assert {"knowledge_sync_schedules", "knowledge_sync_transfer_batches", "knowledge_sync_transfer_chunks", "knowledge_sync_transfer_attempts", "knowledge_sync_dead_letters"}.issubset(Base.metadata.tables)


def test_schedule_requires_trusted_node_and_bounded_concurrency():
    good = evaluate_schedule(node_status="trusted", direction="pull", interval_minutes=60, max_concurrent_runs=2, jitter_seconds=30)
    bad = evaluate_schedule(node_status="suspended", direction="sideways", interval_minutes=1, max_concurrent_runs=10, jitter_seconds=1000)
    assert good["allowed"] is True
    assert bad["allowed"] is False


def test_transfer_plan_respects_item_and_byte_limits():
    result = plan_transfer_chunks(total_items=2500, total_bytes=12_000_000, max_items_per_chunk=1000, max_bytes_per_chunk=5_000_000)
    assert result["chunk_count"] == 3


def test_chunk_replay_and_oversize_are_rejected():
    result = evaluate_chunk(payload_sha256="a"*64, compressed_sha256=None, byte_count=11*1024*1024, item_count=10, idempotency_key="chunk-1", replayed_keys={"chunk-1"})
    assert result["accepted"] is False
    assert "chunk_replay_detected" in result["reason_codes"]


def test_retry_policy_distinguishes_transient_and_permanent_failures():
    retry = evaluate_transfer_retry(attempt_count=2, response_status=503, network_error=False)
    dead = evaluate_transfer_retry(attempt_count=1, response_status=400, network_error=False)
    assert retry["action"] == "retry"
    assert dead["action"] == "dead_letter"


def test_retry_budget_exhaustion_dead_letters():
    result = evaluate_transfer_retry(attempt_count=8, response_status=429, network_error=False)
    assert result["action"] == "dead_letter"


def test_batch_reconciliation_is_deterministic():
    assert reconcile_batch(total_chunks=4, verified_chunks=4, failed_chunks=0)["status"] == "completed"
    assert reconcile_batch(total_chunks=4, verified_chunks=3, failed_chunks=1)["status"] == "partial"


def test_checkpoint_never_advances_with_conflicts_or_dead_letters():
    blocked = evaluate_checkpoint_advance(current_checkpoint="cp-1", proposed_checkpoint="cp-2", batch_status="completed", unresolved_conflicts=1, dead_letters=0)
    allowed = evaluate_checkpoint_advance(current_checkpoint="cp-1", proposed_checkpoint="cp-2", batch_status="completed", unresolved_conflicts=0, dead_letters=0)
    assert blocked["allowed"] is False
    assert allowed["allowed"] is True


def test_chunk_idempotency_key_is_deterministic():
    first = compute_chunk_idempotency_key(run_id="run-1", batch_number=1, chunk_number=2, payload_sha256="b"*64)
    second = compute_chunk_idempotency_key(run_id="run-1", batch_number=1, chunk_number=2, payload_sha256="b"*64)
    assert first == second and len(first) == 64
