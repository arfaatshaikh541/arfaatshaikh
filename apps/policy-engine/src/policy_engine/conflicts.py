"""Static conflict detection between two policies bound to the same tenant
scope (approved architecture §23): before a new policy can be published,
control-api asks whether it and every other currently-published policy for
that tenant could ever *both* be satisfied by some candidate placement. A
conflict here means "no candidate can pass both" -- the tenant's
sovereignty requirements would become impossible to satisfy, not just
merely restrictive.
"""

from __future__ import annotations

from pydantic import BaseModel

from policy_engine.schema import PolicyDocument


class ConflictCheckRequest(BaseModel):
    policy_a_id: str
    policy_a: PolicyDocument
    policy_b_id: str
    policy_b: PolicyDocument


class PolicyConflict(BaseModel):
    code: str
    description: str


class ConflictCheckResult(BaseModel):
    has_conflicts: bool
    conflicts: list[PolicyConflict]


def _disjoint(a: list[str], b: list[str]) -> bool:
    """True if both lists are non-empty and share no element -- i.e. no
    value could ever satisfy an "in this list" check against both.
    """
    return bool(a) and bool(b) and not (set(a) & set(b))


def _cross_contradiction(allowed: list[str], denied: list[str]) -> set[str]:
    """Values present in one policy's allow-list and the other's deny-list
    -- unsatisfiable for that specific value regardless of the rest of
    either list.
    """
    return set(allowed) & set(denied)


def _residency_conflicts(a: PolicyDocument, b: PolicyDocument) -> list[PolicyConflict]:
    conflicts: list[PolicyConflict] = []
    if _disjoint(a.residency.allowed_countries, b.residency.allowed_countries):
        conflicts.append(
            PolicyConflict(
                code="CONTRADICTORY_RESIDENCY_ALLOWED_SETS",
                description=(
                    "The two policies' residency.allowed_countries share no "
                    "country -- no placement could satisfy both."
                ),
            )
        )
    a_allowed_b_denied = _cross_contradiction(
        a.residency.allowed_countries, b.residency.denied_countries
    )
    b_allowed_a_denied = _cross_contradiction(
        b.residency.allowed_countries, a.residency.denied_countries
    )
    for country in sorted(a_allowed_b_denied | b_allowed_a_denied):
        conflicts.append(
            PolicyConflict(
                code="CONTRADICTORY_RESIDENCY_COUNTRY",
                description=(
                    f"Country {country!r} is allowed by one policy and denied by the other."
                ),
            )
        )
    return conflicts


def _operator_conflicts(a: PolicyDocument, b: PolicyDocument) -> list[PolicyConflict]:
    conflicts: list[PolicyConflict] = []
    if _disjoint(a.operators.allowed, b.operators.allowed):
        conflicts.append(
            PolicyConflict(
                code="CONTRADICTORY_OPERATOR_ALLOWED_SETS",
                description=(
                    "The two policies' operators.allowed share no operator "
                    "-- no placement could satisfy both."
                ),
            )
        )
    a_allowed_b_denied = _cross_contradiction(a.operators.allowed, b.operators.denied)
    b_allowed_a_denied = _cross_contradiction(b.operators.allowed, a.operators.denied)
    for operator_id in sorted(a_allowed_b_denied | b_allowed_a_denied):
        conflicts.append(
            PolicyConflict(
                code="CONTRADICTORY_OPERATOR",
                description=(
                    f"Operator {operator_id!r} is allowed by one policy and denied by the other."
                ),
            )
        )
    return conflicts


def _cross_border_conflicts(a: PolicyDocument, b: PolicyDocument) -> list[PolicyConflict]:
    conflicts: list[PolicyConflict] = []
    if _disjoint(a.cross_border.backup_allowed_countries, b.cross_border.backup_allowed_countries):
        conflicts.append(
            PolicyConflict(
                code="CONTRADICTORY_CROSS_BORDER_BACKUP",
                description=(
                    "The two policies' cross_border.backup_allowed_countries share no country."
                ),
            )
        )
    failover_a = a.cross_border.failover_allowed_countries
    failover_b = b.cross_border.failover_allowed_countries
    if _disjoint(failover_a, failover_b):
        conflicts.append(
            PolicyConflict(
                code="CONTRADICTORY_CROSS_BORDER_FAILOVER",
                description=(
                    "The two policies' cross_border.failover_allowed_countries share no country."
                ),
            )
        )
    return conflicts


def _encryption_conflicts(a: PolicyDocument, b: PolicyDocument) -> list[PolicyConflict]:
    a_key = a.encryption.key_ownership
    b_key = b.encryption.key_ownership
    if a_key is not None and b_key is not None and a_key != b_key:
        return [
            PolicyConflict(
                code="CONTRADICTORY_ENCRYPTION_KEY_OWNERSHIP",
                description=(
                    f"One policy requires encryption key ownership {a_key!r}, "
                    f"the other requires {b_key!r} -- mutually exclusive."
                ),
            )
        ]
    return []


def find_conflicts(request: ConflictCheckRequest) -> ConflictCheckResult:
    a, b = request.policy_a, request.policy_b
    conflicts: list[PolicyConflict] = [
        *_residency_conflicts(a, b),
        *_operator_conflicts(a, b),
        *_cross_border_conflicts(a, b),
        *_encryption_conflicts(a, b),
    ]
    return ConflictCheckResult(has_conflicts=bool(conflicts), conflicts=conflicts)
