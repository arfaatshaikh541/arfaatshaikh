from __future__ import annotations

import hashlib
import math
import re

TRANSPORT_POLICY_VERSION = "knowledge-sync-transport-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def evaluate_schedule(*, node_status: str, direction: str, interval_minutes: int, max_concurrent_runs: int, jitter_seconds: int) -> dict[str, object]:
    reasons: list[str] = []
    if node_status != "trusted": reasons.append("trusted_node_required")
    if direction not in {"pull", "push"}: reasons.append("invalid_sync_direction")
    if not 5 <= interval_minutes <= 10080: reasons.append("schedule_interval_out_of_bounds")
    if not 1 <= max_concurrent_runs <= 4: reasons.append("concurrency_limit_out_of_bounds")
    if not 0 <= jitter_seconds <= 900: reasons.append("jitter_out_of_bounds")
    return {"allowed": not reasons, "reason_codes": reasons or ["schedule_allowed"], "policy_version": TRANSPORT_POLICY_VERSION}


def plan_transfer_chunks(*, total_items: int, total_bytes: int, max_items_per_chunk: int, max_bytes_per_chunk: int) -> dict[str, object]:
    if total_items < 0 or total_bytes < 0:
        raise ValueError("transfer totals cannot be negative")
    if not 1 <= max_items_per_chunk <= 1000:
        raise ValueError("max_items_per_chunk out of bounds")
    if not 1024 <= max_bytes_per_chunk <= 10 * 1024 * 1024:
        raise ValueError("max_bytes_per_chunk out of bounds")
    item_chunks = math.ceil(total_items / max_items_per_chunk) if total_items else 0
    byte_chunks = math.ceil(total_bytes / max_bytes_per_chunk) if total_bytes else 0
    chunk_count = max(item_chunks, byte_chunks)
    return {
        "chunk_count": chunk_count,
        "empty_transfer": chunk_count == 0,
        "max_items_per_chunk": max_items_per_chunk,
        "max_bytes_per_chunk": max_bytes_per_chunk,
        "policy_version": TRANSPORT_POLICY_VERSION,
    }


def evaluate_chunk(*, payload_sha256: str, compressed_sha256: str | None, byte_count: int, item_count: int, idempotency_key: str, replayed_keys: set[str]) -> dict[str, object]:
    reasons: list[str] = []
    if not SHA256_RE.fullmatch(payload_sha256): reasons.append("invalid_payload_fingerprint")
    if compressed_sha256 is not None and not SHA256_RE.fullmatch(compressed_sha256): reasons.append("invalid_compressed_fingerprint")
    if not 1 <= byte_count <= 10 * 1024 * 1024: reasons.append("chunk_size_out_of_bounds")
    if not 1 <= item_count <= 1000: reasons.append("chunk_item_count_out_of_bounds")
    if not idempotency_key or len(idempotency_key) > 120: reasons.append("invalid_idempotency_key")
    if idempotency_key in replayed_keys: reasons.append("chunk_replay_detected")
    return {"accepted": not reasons, "reason_codes": reasons or ["chunk_accepted"], "policy_version": TRANSPORT_POLICY_VERSION}


def evaluate_transfer_retry(*, attempt_count: int, response_status: int | None, network_error: bool, cancelled: bool = False) -> dict[str, object]:
    if not 0 <= attempt_count <= 8:
        raise ValueError("attempt_count out of bounds")
    if response_status is not None and not 100 <= response_status <= 599:
        raise ValueError("invalid response status")
    if cancelled:
        return {"action": "cancel", "retry_after_seconds": None, "reason_codes": ["transfer_cancelled"], "policy_version": TRANSPORT_POLICY_VERSION}
    transient = network_error or response_status == 429 or (response_status is not None and 500 <= response_status <= 599)
    if transient and attempt_count < 8:
        delay = min(900, 2 ** max(attempt_count, 1))
        return {"action": "retry", "retry_after_seconds": delay, "reason_codes": ["transient_transfer_failure"], "policy_version": TRANSPORT_POLICY_VERSION}
    if transient:
        return {"action": "dead_letter", "retry_after_seconds": None, "reason_codes": ["retry_budget_exhausted"], "policy_version": TRANSPORT_POLICY_VERSION}
    if response_status is not None and 200 <= response_status <= 299:
        return {"action": "complete", "retry_after_seconds": None, "reason_codes": ["transfer_succeeded"], "policy_version": TRANSPORT_POLICY_VERSION}
    return {"action": "dead_letter", "retry_after_seconds": None, "reason_codes": ["permanent_transfer_failure"], "policy_version": TRANSPORT_POLICY_VERSION}


def reconcile_batch(*, total_chunks: int, verified_chunks: int, failed_chunks: int, cancelled_chunks: int = 0) -> dict[str, object]:
    values = (total_chunks, verified_chunks, failed_chunks, cancelled_chunks)
    if any(value < 0 for value in values) or verified_chunks + failed_chunks + cancelled_chunks > total_chunks:
        raise ValueError("invalid batch counters")
    pending = total_chunks - verified_chunks - failed_chunks - cancelled_chunks
    if cancelled_chunks and pending == 0: status = "cancelled"
    elif failed_chunks and pending == 0: status = "partial" if verified_chunks else "failed"
    elif total_chunks == verified_chunks: status = "completed"
    elif verified_chunks or failed_chunks: status = "transferring"
    else: status = "planned"
    return {"status": status, "pending_chunks": pending, "policy_version": TRANSPORT_POLICY_VERSION}


def evaluate_checkpoint_advance(*, current_checkpoint: str | None, proposed_checkpoint: str | None, batch_status: str, unresolved_conflicts: int, dead_letters: int) -> dict[str, object]:
    reasons: list[str] = []
    if batch_status != "completed": reasons.append("completed_batch_required")
    if unresolved_conflicts: reasons.append("unresolved_conflicts_present")
    if dead_letters: reasons.append("dead_letters_present")
    if proposed_checkpoint is None or not proposed_checkpoint.strip() or len(proposed_checkpoint) > 200: reasons.append("valid_next_checkpoint_required")
    if proposed_checkpoint == current_checkpoint: reasons.append("checkpoint_must_advance")
    return {"allowed": not reasons, "reason_codes": reasons or ["checkpoint_advance_allowed"], "policy_version": TRANSPORT_POLICY_VERSION}


def compute_chunk_idempotency_key(*, run_id: str, batch_number: int, chunk_number: int, payload_sha256: str) -> str:
    if batch_number < 1 or chunk_number < 1 or not SHA256_RE.fullmatch(payload_sha256):
        raise ValueError("valid batch, chunk and payload fingerprint required")
    canonical = f"{run_id}:{batch_number}:{chunk_number}:{payload_sha256}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
