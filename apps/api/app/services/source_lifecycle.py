from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievalEligibility:
    source_approved: bool
    licence_approved: bool
    redistribution_allowed: bool
    acquisition_recorded: bool
    integrity_verified: bool
    ingestion_ready: bool
    review_approved: bool
    attribution_present: bool
    policy_present: bool = False
    policy_reviewers_met: bool = False
    policy_domains_met: bool = False

    @property
    def eligible(self) -> bool:
        return all(
            (
                self.source_approved,
                self.licence_approved,
                self.redistribution_allowed,
                self.acquisition_recorded,
                self.integrity_verified,
                self.ingestion_ready,
                self.review_approved,
                self.attribution_present,
                self.policy_present,
                self.policy_reviewers_met,
                self.policy_domains_met,
            )
        )

    def failed_gates(self) -> list[str]:
        values = {
            "source_approved": self.source_approved,
            "licence_approved": self.licence_approved,
            "redistribution_allowed": self.redistribution_allowed,
            "acquisition_recorded": self.acquisition_recorded,
            "integrity_verified": self.integrity_verified,
            "ingestion_ready": self.ingestion_ready,
            "review_approved": self.review_approved,
            "attribution_present": self.attribution_present,
            "policy_present": self.policy_present,
            "policy_reviewers_met": self.policy_reviewers_met,
            "policy_domains_met": self.policy_domains_met,
        }
        return [name for name, passed in values.items() if not passed]


_ALLOWED_INGESTION_TRANSITIONS: dict[str, set[str]] = {
    "not_started": {"registered"},
    "registered": {"validating", "blocked", "retired"},
    "validating": {"ready", "blocked", "retired"},
    "ready": {"blocked", "retired"},
    "blocked": {"validating", "retired"},
    "retired": set(),
}


def ingestion_transition_allowed(current: str, target: str) -> bool:
    return target in _ALLOWED_INGESTION_TRANSITIONS.get(current, set())
