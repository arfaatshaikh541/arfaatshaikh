from __future__ import annotations

import hashlib
import json
import re

INTEGRITY_POLICY_VERSION = "knowledge-sync-integrity-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SENSITIVE_TYPES = {"quran", "hadith", "tafsir", "fiqh"}


def compute_partition_digest(*, partition_key: str, ordered_items: list[dict[str, str]]) -> str:
    if not partition_key.strip() or len(partition_key) > 160:
        raise ValueError("invalid partition key")
    canonical_items: list[dict[str, str]] = []
    previous = None
    for item in ordered_items:
        canonical_id = item.get("canonical_id", "")
        payload_sha256 = item.get("payload_sha256", "")
        if not canonical_id or not SHA256_RE.fullmatch(payload_sha256):
            raise ValueError("valid canonical ids and fingerprints required")
        if previous is not None and canonical_id <= previous:
            raise ValueError("items must be strictly ordered by canonical_id")
        previous = canonical_id
        canonical_items.append({"canonical_id": canonical_id, "payload_sha256": payload_sha256})
    payload = json.dumps({"partition_key": partition_key, "items": canonical_items}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_snapshot_root(*, content_type: str, snapshot_version: str, partition_digests: list[dict[str, str]]) -> str:
    if not content_type.strip() or not snapshot_version.strip():
        raise ValueError("content type and snapshot version required")
    ordered = sorted(partition_digests, key=lambda value: value.get("partition_key", ""))
    if len({item.get("partition_key") for item in ordered}) != len(ordered):
        raise ValueError("duplicate partition keys are not allowed")
    for item in ordered:
        if not item.get("partition_key") or not SHA256_RE.fullmatch(item.get("digest_sha256", "")):
            raise ValueError("valid partition digests required")
    payload = json.dumps({"content_type": content_type, "snapshot_version": snapshot_version, "partitions": ordered}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def evaluate_snapshot_seal(*, node_status: str, content_type: str, root_sha256: str, item_count: int, partition_count: int, calculated_partition_count: int) -> dict[str, object]:
    reasons: list[str] = []
    if node_status != "trusted": reasons.append("trusted_node_required")
    if not SHA256_RE.fullmatch(root_sha256): reasons.append("invalid_snapshot_root")
    if not 0 <= item_count <= 10_000_000: reasons.append("snapshot_item_count_out_of_bounds")
    if not 1 <= partition_count <= 100_000: reasons.append("snapshot_partition_count_out_of_bounds")
    if partition_count != calculated_partition_count: reasons.append("partition_count_mismatch")
    if not content_type.strip(): reasons.append("content_type_required")
    return {"allowed": not reasons, "reason_codes": reasons or ["snapshot_seal_allowed"], "policy_version": INTEGRITY_POLICY_VERSION}


def compare_snapshots(*, local_root_sha256: str, remote_root_sha256: str, local_partitions: dict[str, str], remote_partitions: dict[str, str]) -> dict[str, object]:
    if not SHA256_RE.fullmatch(local_root_sha256) or not SHA256_RE.fullmatch(remote_root_sha256):
        raise ValueError("valid snapshot roots required")
    for value in [*local_partitions.values(), *remote_partitions.values()]:
        if not SHA256_RE.fullmatch(value): raise ValueError("valid partition digests required")
    keys = sorted(set(local_partitions) | set(remote_partitions))
    matching = [key for key in keys if key in local_partitions and key in remote_partitions and local_partitions[key] == remote_partitions[key]]
    divergent = [key for key in keys if key in local_partitions and key in remote_partitions and local_partitions[key] != remote_partitions[key]]
    missing_local = [key for key in keys if key not in local_partitions]
    missing_remote = [key for key in keys if key not in remote_partitions]
    clean = local_root_sha256 == remote_root_sha256 and not divergent and not missing_local and not missing_remote
    return {"status": "clean" if clean else "drift_detected", "matching_partitions": matching, "divergent_partitions": divergent, "missing_local_partitions": missing_local, "missing_remote_partitions": missing_remote, "policy_version": INTEGRITY_POLICY_VERSION}


def evaluate_repair_plan(*, content_type: str, strategy: str, partition_keys: list[str], drift_status: str, scholarly_approved: bool, automatic_replacement: bool) -> dict[str, object]:
    reasons: list[str] = []
    if drift_status != "drift_detected": reasons.append("active_drift_required")
    if strategy not in {"fetch_missing", "replace_divergent", "manual_review"}: reasons.append("invalid_repair_strategy")
    if not partition_keys or len(partition_keys) > 10000 or len(set(partition_keys)) != len(partition_keys): reasons.append("valid_unique_partitions_required")
    sensitive = content_type in SENSITIVE_TYPES
    if sensitive and strategy == "replace_divergent" and not scholarly_approved: reasons.append("scholarly_approval_required")
    if sensitive and automatic_replacement: reasons.append("automatic_sensitive_replacement_forbidden")
    if strategy == "manual_review" and automatic_replacement: reasons.append("manual_review_cannot_auto_execute")
    return {"allowed": not reasons, "requires_scholarly_review": sensitive, "reason_codes": reasons or ["repair_plan_allowed"], "policy_version": INTEGRITY_POLICY_VERSION}


def verify_snapshot_integrity(*, expected_root_sha256: str, calculated_root_sha256: str, expected_partitions: int, verified_partitions: int, unresolved_drift: int) -> dict[str, object]:
    reasons: list[str] = []
    if not SHA256_RE.fullmatch(expected_root_sha256) or not SHA256_RE.fullmatch(calculated_root_sha256): reasons.append("invalid_snapshot_root")
    if expected_partitions < 1 or verified_partitions < 0 or verified_partitions > expected_partitions: reasons.append("invalid_partition_verification_counts")
    if expected_root_sha256 != calculated_root_sha256: reasons.append("snapshot_root_mismatch")
    if verified_partitions != expected_partitions: reasons.append("partition_verification_incomplete")
    if unresolved_drift: reasons.append("unresolved_drift_present")
    return {"outcome": "passed" if not reasons else "failed", "reason_codes": reasons or ["snapshot_integrity_verified"], "policy_version": INTEGRITY_POLICY_VERSION}
