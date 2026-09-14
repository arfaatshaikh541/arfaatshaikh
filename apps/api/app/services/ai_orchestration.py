from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

ORCHESTRATION_POLICY_VERSION = "evidence-orchestration-v1"
GROUNDING_POLICY_VERSION = "claim-citation-gate-v2"

ALLOWED_CLAIM_TYPES = {
    "direct_quote", "source_summary", "scholarly_interpretation",
    "difference_of_opinion", "general_explanation", "ruling",
}

@dataclass(frozen=True)
class CitationEvidence:
    source_passage_id: str
    corpus_type: str
    exact_text: str
    attribution: str
    evidence_sha256: str

@dataclass(frozen=True)
class ClaimCandidate:
    claim_type: str
    text: str
    evidence_indices: tuple[int, ...]

@dataclass(frozen=True)
class ClaimDecision:
    position: int
    decision: str
    reason_code: str
    citation_labels: tuple[str, ...]

@dataclass(frozen=True)
class OrchestrationDecision:
    status: str
    requires_scholar: bool
    terminal_reason: str | None
    claims: tuple[ClaimDecision, ...]


def sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _validate_evidence(item: CitationEvidence) -> None:
    if not item.source_passage_id.strip():
        raise ValueError("citation requires a governed source passage")
    if not item.attribution.strip():
        raise ValueError("citation requires attribution")
    if sha256_text(item.exact_text) != item.evidence_sha256:
        raise ValueError("citation evidence fingerprint mismatch")


def evaluate_claim(position: int, claim: ClaimCandidate, evidence: tuple[CitationEvidence, ...], *, high_risk: bool) -> ClaimDecision:
    if claim.claim_type not in ALLOWED_CLAIM_TYPES:
        return ClaimDecision(position, "blocked", "unsupported_claim_type", ())
    if not claim.text.strip():
        return ClaimDecision(position, "blocked", "empty_claim", ())
    if not claim.evidence_indices:
        return ClaimDecision(position, "blocked", "claim_has_no_citation", ())
    if any(index < 0 or index >= len(evidence) for index in claim.evidence_indices):
        return ClaimDecision(position, "blocked", "citation_index_out_of_range", ())

    selected = tuple(evidence[index] for index in claim.evidence_indices)
    try:
        for item in selected:
            _validate_evidence(item)
    except ValueError as exc:
        return ClaimDecision(position, "blocked", str(exc).replace(" ", "_"), ())

    if claim.claim_type == "direct_quote" and not any(claim.text.strip() in item.exact_text for item in selected):
        return ClaimDecision(position, "blocked", "quote_not_verbatim_in_evidence", ())
    if claim.claim_type == "scholarly_interpretation" and not any(item.corpus_type == "tafsir" for item in selected):
        return ClaimDecision(position, "blocked", "interpretation_requires_tafsir", ())
    if claim.claim_type == "difference_of_opinion":
        attributions = {item.attribution.strip() for item in selected}
        if len(attributions) < 2:
            return ClaimDecision(position, "blocked", "difference_requires_distinct_attributions", ())
    if claim.claim_type == "ruling" or high_risk:
        return ClaimDecision(position, "escalated", "personal_ruling_requires_qualified_scholar", tuple(f"[{i + 1}]" for i in claim.evidence_indices))

    return ClaimDecision(position, "verified", "claim_supported", tuple(f"[{i + 1}]" for i in claim.evidence_indices))


def orchestrate_claims(claims: Iterable[ClaimCandidate], evidence: Iterable[CitationEvidence], *, risk_level: str) -> OrchestrationDecision:
    evidence_tuple = tuple(evidence)
    claim_tuple = tuple(claims)
    if not evidence_tuple:
        return OrchestrationDecision("blocked", False, "no_governed_evidence", ())
    if not claim_tuple:
        return OrchestrationDecision("blocked", False, "no_claims", ())

    high_risk = risk_level == "high_risk"
    decisions = tuple(evaluate_claim(i, claim, evidence_tuple, high_risk=high_risk) for i, claim in enumerate(claim_tuple))
    if any(item.decision == "blocked" for item in decisions):
        first = next(item for item in decisions if item.decision == "blocked")
        return OrchestrationDecision("blocked", False, first.reason_code, decisions)
    if any(item.decision == "escalated" for item in decisions):
        return OrchestrationDecision("escalated", True, "qualified_scholar_review_required", decisions)
    return OrchestrationDecision("completed", False, None, decisions)
