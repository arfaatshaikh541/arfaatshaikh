"""Detection rules. Each takes the batch of new audit entries since the
last check and returns a reason string if it fires, else None.
Deterministic thresholds, not model judgment — an anomaly-scoring model
is legitimate future work (docs/architecture/04-agent-architecture.md
#security-guardian-independent-oversight) but a rule hit should be an
instant, explainable freeze, not a probabilistic guess.
"""
from __future__ import annotations

from collections import Counter
from typing import Protocol

from ..governance.models import AuditEntry


class GuardianRule(Protocol):
    name: str

    def check(self, entries: list[AuditEntry]) -> str | None: ...


class RepeatedDenialsRule:
    """Many DENIED/RATE_LIMITED results for the same actor in one batch:
    could be a misconfigured caller hammering a blocked action, or a
    compromised/malicious agent probing for a gap in policy."""

    name = "repeated_denials"

    def __init__(self, threshold: int = 5) -> None:
        self._threshold = threshold

    def check(self, entries: list[AuditEntry]) -> str | None:
        denied_statuses = {"DENIED", "RATE_LIMITED"}
        counts = Counter(e.actor for e in entries if e.result_status in denied_statuses)
        for actor, count in counts.items():
            if count >= self._threshold:
                return f"actor '{actor}' had {count} denied/rate-limited actions in one check window (threshold {self._threshold})"
        return None


class RedTierVelocityRule:
    """A burst of RED-tier requests, even individually pending approval,
    is itself a signal worth freezing on — approval fatigue is a named
    failure mode (docs/threat-model/failure-scenarios.md #48), and a
    burst is exactly the pattern that induces it."""

    name = "red_tier_velocity"

    def __init__(self, threshold: int = 3) -> None:
        self._threshold = threshold

    def check(self, entries: list[AuditEntry]) -> str | None:
        red_count = sum(1 for e in entries if e.risk_tier == "RED")
        if red_count >= self._threshold:
            return f"{red_count} RED-tier action requests in one check window (threshold {self._threshold})"
        return None


DEFAULT_RULES: list[GuardianRule] = [RepeatedDenialsRule(), RedTierVelocityRule()]
