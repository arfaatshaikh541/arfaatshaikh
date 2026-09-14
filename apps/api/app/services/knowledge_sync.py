from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from urllib.parse import urlparse

SYNC_POLICY_VERSION = "knowledge-sync-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ALLOWED_CONTENT_TYPES = {"quran", "hadith", "tafsir", "fiqh", "biography", "course", "research", "knowledge_entity"}


def _public_https(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".local"):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast)


def evaluate_sync_node(*, slug: str, base_url: str, public_key_fingerprint: str, organisation_active: bool, independent_verification: bool) -> dict[str, object]:
    reasons: list[str] = []
    if not SLUG_RE.fullmatch(slug): reasons.append("invalid_node_slug")
    if not _public_https(base_url): reasons.append("public_https_base_url_required")
    if not SHA256_RE.fullmatch(public_key_fingerprint): reasons.append("valid_public_key_fingerprint_required")
    if not organisation_active: reasons.append("active_organisation_required")
    if not independent_verification: reasons.append("independent_node_verification_required")
    return {"trusted": not reasons, "reason_codes": reasons or ["sync_node_trusted"], "policy_version": SYNC_POLICY_VERSION}


def evaluate_trust_policy(*, node_status: str, direction: str, content_types: set[str], require_signature: bool, require_scholarly_approval: bool, max_items_per_run: int) -> dict[str, object]:
    reasons: list[str] = []
    if node_status != "trusted": reasons.append("trusted_node_required")
    if direction not in {"pull", "push", "bidirectional"}: reasons.append("invalid_sync_direction")
    if not content_types: reasons.append("content_type_required")
    if content_types - ALLOWED_CONTENT_TYPES: reasons.append("unsupported_content_type")
    if not require_signature: reasons.append("signature_verification_required")
    sensitive = {"quran", "hadith", "tafsir", "fiqh"}
    if content_types & sensitive and not require_scholarly_approval: reasons.append("scholarly_approval_required")
    if not 1 <= max_items_per_run <= 10000: reasons.append("item_limit_out_of_bounds")
    return {"allowed": not reasons, "reason_codes": reasons or ["trust_policy_allowed"], "policy_version": SYNC_POLICY_VERSION}


def validate_manifest(*, manifest_sha256: str, item_count: int, checkpoint: str | None, request_id: str, replayed_request_ids: set[str]) -> dict[str, object]:
    reasons: list[str] = []
    if not SHA256_RE.fullmatch(manifest_sha256): reasons.append("invalid_manifest_fingerprint")
    if not 0 <= item_count <= 10000: reasons.append("manifest_item_count_out_of_bounds")
    if not request_id or len(request_id) > 100: reasons.append("invalid_request_id")
    if request_id in replayed_request_ids: reasons.append("replay_detected")
    if checkpoint is not None and (not checkpoint.strip() or len(checkpoint) > 200): reasons.append("invalid_checkpoint")
    return {"accepted": not reasons, "reason_codes": reasons or ["manifest_accepted"], "policy_version": SYNC_POLICY_VERSION}


def evaluate_sync_item(*, content_type: str, payload_sha256: str, signature_valid: bool, content_version: str, scholarly_approved: bool, local_payload_sha256: str | None = None) -> dict[str, object]:
    reasons: list[str] = []
    if content_type not in ALLOWED_CONTENT_TYPES: reasons.append("unsupported_content_type")
    if not SHA256_RE.fullmatch(payload_sha256): reasons.append("invalid_payload_fingerprint")
    if not signature_valid: reasons.append("invalid_item_signature")
    if not content_version or len(content_version) > 80: reasons.append("invalid_content_version")
    if content_type in {"quran", "hadith", "tafsir", "fiqh"} and not scholarly_approved: reasons.append("scholarly_approval_required")
    conflict = local_payload_sha256 is not None and local_payload_sha256 != payload_sha256
    if conflict: reasons.append("content_conflict_detected")
    return {"accepted": not reasons, "conflict": conflict, "reason_codes": reasons or ["sync_item_accepted"], "policy_version": SYNC_POLICY_VERSION}


def resolve_conflict(*, local_version: str, remote_version: str, local_sha256: str, remote_sha256: str, remote_scholarly_approved: bool, manual_override: str | None = None) -> dict[str, object]:
    for value in (local_sha256, remote_sha256):
        if not SHA256_RE.fullmatch(value):
            raise ValueError("valid SHA-256 fingerprints are required")
    if local_sha256 == remote_sha256:
        return {"resolution": "keep_local", "reason_codes": ["identical_content"], "policy_version": SYNC_POLICY_VERSION}
    if manual_override in {"keep_local", "accept_remote", "manual_merge", "reject_remote"}:
        return {"resolution": manual_override, "reason_codes": ["authorised_manual_resolution"], "policy_version": SYNC_POLICY_VERSION}
    if not remote_scholarly_approved:
        return {"resolution": "reject_remote", "reason_codes": ["remote_scholarly_approval_missing"], "policy_version": SYNC_POLICY_VERSION}
    if remote_version == local_version:
        return {"resolution": "pending", "reason_codes": ["same_version_divergent_content"], "policy_version": SYNC_POLICY_VERSION}
    return {"resolution": "pending", "reason_codes": ["manual_conflict_review_required"], "policy_version": SYNC_POLICY_VERSION}


def compute_audit_event_hash(*, run_id: str, sequence_number: int, event_type: str, evidence_sha256: str, previous_event_sha256: str | None, metadata: dict[str, object]) -> str:
    if sequence_number < 1 or not SHA256_RE.fullmatch(evidence_sha256):
        raise ValueError("valid sequence and evidence fingerprint are required")
    if previous_event_sha256 is not None and not SHA256_RE.fullmatch(previous_event_sha256):
        raise ValueError("invalid previous event fingerprint")
    canonical = json.dumps({"run_id": run_id, "sequence_number": sequence_number, "event_type": event_type, "evidence_sha256": evidence_sha256, "previous_event_sha256": previous_event_sha256, "metadata": metadata}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
