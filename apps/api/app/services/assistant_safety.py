from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Iterable

SAFETY_POLICY_VERSION = "islamic-safety-v1"
RETENTION_POLICY_VERSION = "assistant-retention-v1"

class SafetyAction(str, Enum):
    ALLOW = "allow"
    RESTRICT = "restrict"
    ESCALATE = "escalate"
    REFUSE = "refuse"

@dataclass(frozen=True)
class SafetyDecision:
    action: SafetyAction
    policy_category: str
    reasons: tuple[str, ...]
    raw_question_retention_days: int
    requires_human_scholar: bool

_INJECTION = re.compile(r"(ignore (all|any|previous|system) instructions|reveal (the )?(system|hidden) prompt|answer without evidence|do not cite|override safety)", re.I)
_VIOLENCE = re.compile(r"\b(kill|attack|bomb|terror|behead|violent revenge)\b", re.I)
_TAKFIR = re.compile(r"\b(takfir|declare .* kafir|is .* kafir)\b", re.I)
_PRIVACY = re.compile(r"\b(my spouse|my husband|my wife|my child|my medical|my diagnosis|my divorce|my abuse)\b", re.I)


def detect_inert_source_instructions(text: str) -> tuple[str, ...]:
    """Return suspicious instruction-like spans. They remain quoted data and are never executed."""
    return tuple(match.group(0) for match in _INJECTION.finditer(text))


def evaluate_safety(question: str, classification: str, retrieved_texts: Iterable[str] = ()) -> SafetyDecision:
    reasons: list[str] = []
    if _INJECTION.search(question):
        reasons.append("user_prompt_injection_attempt")
    contaminated = any(detect_inert_source_instructions(text) for text in retrieved_texts)
    if contaminated:
        reasons.append("retrieved_instruction_like_text_is_inert")
    if _VIOLENCE.search(question):
        return SafetyDecision(SafetyAction.REFUSE, "unsafe_request", tuple(reasons + ["violent_harm_request"]), 0, False)
    if _TAKFIR.search(question):
        return SafetyDecision(SafetyAction.RESTRICT, "sectarian_difference", tuple(reasons + ["takfir_requires_strict_scope"]), 7, True)
    if classification == "high_risk_fatwa":
        return SafetyDecision(SafetyAction.ESCALATE, "high_risk_fatwa", tuple(reasons + ["case_specific_ruling_requires_qualified_scholar"]), 7, True)
    if classification == "unsupported":
        return SafetyDecision(SafetyAction.REFUSE, "unsupported_request", tuple(reasons + ["outside_supported_scope"]), 0, False)
    retention = 7 if _PRIVACY.search(question) else 30
    category = "privacy_sensitive" if retention == 7 else "standard_information"
    action = SafetyAction.RESTRICT if reasons else SafetyAction.ALLOW
    return SafetyDecision(action, category, tuple(reasons), retention, False)


def validate_disagreement_sections(sections: list[dict[str, object]]) -> None:
    if len(sections) < 2:
        raise ValueError("a disagreement presentation requires at least two separately attributed views")
    attributions = {str(section.get("attribution", "")).strip() for section in sections}
    if "" in attributions or len(attributions) < 2:
        raise ValueError("each disagreement view requires a distinct attribution")
    for section in sections:
        if not section.get("evidence_labels"):
            raise ValueError("each disagreement view requires cited evidence")
