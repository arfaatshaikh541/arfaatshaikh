"""Deterministic sovereignty-policy evaluation pipeline (approved
architecture §22-23).

Every constraint function is a pure function: same policy + candidate in,
same reason codes out, always. The overall decision is deny-by-default --
ALLOW requires every constraint to explicitly pass; any single failure (or
an empty/ambiguous input) denies. All failing reason codes are collected,
not just the first, so the caller gets a full explanation trace rather than
having to re-run evaluation to find the next blocking constraint.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime

from policy_engine.schema import (
    Decision,
    EvaluationCandidate,
    EvaluationRequest,
    EvaluationResult,
    PolicyDocument,
)

ConstraintCheck = Callable[[PolicyDocument, EvaluationCandidate], list[str]]


def _check_residency(policy: PolicyDocument, candidate: EvaluationCandidate) -> list[str]:
    residency = policy.residency
    if candidate.country in residency.denied_countries:
        return ["RESIDENCY_DENIED_COUNTRY"]
    if residency.allowed_countries and candidate.country not in residency.allowed_countries:
        return ["RESIDENCY_NOT_IN_ALLOWED_COUNTRIES"]
    return []


def _check_operators(policy: PolicyDocument, candidate: EvaluationCandidate) -> list[str]:
    operators = policy.operators
    if candidate.operator_id in operators.denied:
        return ["OPERATOR_DENIED"]
    if operators.allowed and candidate.operator_id not in operators.allowed:
        return ["OPERATOR_NOT_IN_ALLOWED_LIST"]
    return []


def _check_confidential_computing(
    policy: PolicyDocument, candidate: EvaluationCandidate
) -> list[str]:
    if policy.confidential_computing.required and not candidate.confidential_computing_available:
        return ["CONFIDENTIAL_COMPUTING_REQUIRED_BUT_UNAVAILABLE"]
    return []


def _check_cross_border(policy: PolicyDocument, candidate: EvaluationCandidate) -> list[str]:
    cross_border = policy.cross_border
    if candidate.placement_role == "backup" and cross_border.backup_allowed_countries:
        if candidate.country not in cross_border.backup_allowed_countries:
            return ["CROSS_BORDER_BACKUP_NOT_ALLOWED"]
    if candidate.placement_role == "failover" and cross_border.failover_allowed_countries:
        if candidate.country not in cross_border.failover_allowed_countries:
            return ["CROSS_BORDER_FAILOVER_NOT_ALLOWED"]
    return []


def _check_encryption(policy: PolicyDocument, candidate: EvaluationCandidate) -> list[str]:
    required_ownership = policy.encryption.key_ownership
    if required_ownership is None:
        return []
    # Fail closed: a candidate that doesn't declare its key-ownership
    # capability cannot be assumed to satisfy an explicit requirement.
    if candidate.encryption_key_ownership != required_ownership:
        return ["ENCRYPTION_KEY_OWNERSHIP_MISMATCH"]
    return []


# Ordered pipeline -- order only affects the order reason codes are
# collected in, never the final decision (every check always runs).
CONSTRAINT_PIPELINE: list[ConstraintCheck] = [
    _check_residency,
    _check_operators,
    _check_confidential_computing,
    _check_cross_border,
    _check_encryption,
]


def compute_inputs_hash(request: EvaluationRequest) -> str:
    canonical = request.model_dump_json(exclude_none=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evaluate(request: EvaluationRequest) -> EvaluationResult:
    reason_codes: list[str] = []
    for check in CONSTRAINT_PIPELINE:
        reason_codes.extend(check(request.policy, request.candidate))

    decision: Decision = "deny" if reason_codes else "allow"
    return EvaluationResult(
        decision=decision,
        reason_codes=reason_codes,
        policy_id=request.policy_id,
        policy_version=request.policy_version,
        inputs_hash=compute_inputs_hash(request),
        evaluated_at=datetime.now(UTC).isoformat(),
    )
