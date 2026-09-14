from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Sequence

from app.services.retrieval import EvidenceContract, sha256_text, validate_evidence_contract

CLASSIFIER_VERSION = "question-classifier-v1"
GROUNDING_POLICY_VERSION = "claim-grounding-v1"


class QuestionClass(str, Enum):
    QURAN_EXPLANATION = "quran_explanation"
    HADITH_EXPLANATION = "hadith_explanation"
    AQIDAH = "aqidah"
    FIQH = "fiqh"
    SEERAH = "seerah"
    ISLAMIC_HISTORY = "islamic_history"
    ETHICS_SPIRITUALITY = "ethics_spirituality"
    COMPARATIVE_RELIGION = "comparative_religion"
    PERSONAL_GUIDANCE = "personal_guidance"
    HIGH_RISK_FATWA = "high_risk_fatwa"
    DISPUTED_ISSUE = "disputed_issue"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class ClassificationResult:
    classification: QuestionClass
    risk_level: str
    required_corpora: tuple[str, ...]
    requires_escalation: bool


@dataclass(frozen=True)
class ClaimDraft:
    claim_type: str
    text: str
    evidence_indices: tuple[int, ...]


@dataclass(frozen=True)
class VerifiedClaim:
    position: int
    claim_type: str
    text: str
    citations: tuple[str, ...]


@dataclass(frozen=True)
class AssemblyResult:
    status: str
    classification: ClassificationResult
    response_text: str | None
    claims: tuple[VerifiedClaim, ...]
    insufficiency_reason: str | None


_HIGH_RISK = re.compile(r"\b(divorc(?:e|ed)|talaq|inheritance|takfir|kafir|marriage valid|nikah valid|custody|oath|vow|financial contract|mortgage|abortion|fasting exemption)\b", re.I)
_DISPUTED = re.compile(r"\b(sect|madhhab|school of thought|scholars differ|difference of opinion|sunni|shia|salafi|sufi)\b", re.I)
_PATTERNS = (
    (QuestionClass.QURAN_EXPLANATION, re.compile(r"\b(qur.?an|ayah|verse|surah|tafsir)\b", re.I), ("quran", "tafsir")),
    (QuestionClass.HADITH_EXPLANATION, re.compile(r"\b(hadith|sunnah|narration|isnad)\b", re.I), ("hadith",)),
    (QuestionClass.AQIDAH, re.compile(r"\b(aqidah|creed|allah|tawhid|qadr|afterlife)\b", re.I), ("quran", "hadith", "tafsir")),
    (QuestionClass.SEERAH, re.compile(r"\b(seerah|prophet.?s life|hijrah|battle of)\b", re.I), ("hadith", "tafsir")),
    (QuestionClass.ISLAMIC_HISTORY, re.compile(r"\b(caliph|companion|islamic history|umayyad|abbasid)\b", re.I), ("hadith", "tafsir")),
    (QuestionClass.COMPARATIVE_RELIGION, re.compile(r"\b(christian|jew|bible|torah|hindu|atheis|comparative religion)\b", re.I), ("quran", "hadith", "tafsir")),
    (QuestionClass.FIQH, re.compile(r"\b(halal|haram|ruling|wudu|salah|zakat|fast|hajj|fiqh)\b", re.I), ("quran", "hadith", "tafsir")),
    (QuestionClass.ETHICS_SPIRITUALITY, re.compile(r"\b(character|patience|gratitude|repent|dua|spiritual|ethic)\b", re.I), ("quran", "hadith", "tafsir")),
)


def classify_question(question: str) -> ClassificationResult:
    normalized = " ".join(question.split())
    if not normalized:
        return ClassificationResult(QuestionClass.UNSUPPORTED, "standard", (), False)
    if _HIGH_RISK.search(normalized):
        return ClassificationResult(QuestionClass.HIGH_RISK_FATWA, "high_risk", ("quran", "hadith", "tafsir"), True)
    if _DISPUTED.search(normalized):
        return ClassificationResult(QuestionClass.DISPUTED_ISSUE, "sensitive", ("quran", "hadith", "tafsir"), False)
    for classification, pattern, corpora in _PATTERNS:
        if pattern.search(normalized):
            return ClassificationResult(classification, "standard", corpora, False)
    if re.search(r"\b(should i|can i|my family|my husband|my wife|my parents)\b", normalized, re.I):
        return ClassificationResult(QuestionClass.PERSONAL_GUIDANCE, "sensitive", ("quran", "hadith", "tafsir"), False)
    return ClassificationResult(QuestionClass.UNSUPPORTED, "standard", (), False)


def _validate_claim(claim: ClaimDraft, evidence: Sequence[EvidenceContract]) -> tuple[str, ...]:
    allowed_types = {"direct_quote", "source_summary", "scholarly_interpretation", "difference_of_opinion", "general_explanation"}
    if claim.claim_type not in allowed_types:
        raise ValueError("unsupported claim type")
    if not claim.text.strip():
        raise ValueError("claim text cannot be empty")
    if not claim.evidence_indices:
        raise ValueError("every religious claim requires evidence")
    selected = []
    for index in claim.evidence_indices:
        if index < 0 or index >= len(evidence):
            raise ValueError("claim references unavailable evidence")
        contract = evidence[index]
        validate_evidence_contract(contract)
        selected.append(contract)
    if claim.claim_type == "direct_quote":
        normalized_claim = " ".join(claim.text.split())
        if not any(normalized_claim in " ".join(item.exact_text.split()) for item in selected):
            raise ValueError("direct quote is not present verbatim in cited evidence")
    if claim.claim_type == "scholarly_interpretation" and not any(item.corpus_type == "tafsir" for item in selected):
        raise ValueError("scholarly interpretation requires tafsir evidence")
    if claim.claim_type == "difference_of_opinion" and len({item.attribution for item in selected}) < 2:
        raise ValueError("difference of opinion requires at least two distinct attributions")
    return tuple(f"[{index + 1}]" for index in claim.evidence_indices)


def assemble_grounded_answer(question: str, evidence: Sequence[EvidenceContract], claims: Sequence[ClaimDraft]) -> AssemblyResult:
    classification = classify_question(question)
    if classification.classification == QuestionClass.UNSUPPORTED:
        return AssemblyResult("insufficient", classification, None, (), "question_outside_supported_islamic_scope")
    if not evidence:
        return AssemblyResult("insufficient", classification, None, (), "no_approved_evidence")
    verified = []
    try:
        for position, claim in enumerate(claims):
            citations = _validate_claim(claim, evidence)
            verified.append(VerifiedClaim(position, claim.claim_type, claim.text.strip(), citations))
    except ValueError as exc:
        return AssemblyResult("insufficient", classification, None, (), str(exc))
    if not verified:
        return AssemblyResult("insufficient", classification, None, (), "no_grounded_claims")
    lines = [f"{claim.text} {' '.join(claim.citations)}" for claim in verified]
    if classification.requires_escalation:
        lines.append("This is general, source-based information, not a personal fatwa. A qualified scholar should review the full circumstances.")
    return AssemblyResult("assembled", classification, "\n\n".join(lines), tuple(verified), None)


def answer_checksum(result: AssemblyResult) -> str | None:
    return sha256_text(result.response_text) if result.response_text is not None else None
