from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
import unicodedata

LANGUAGE_POLICY_VERSION = "multilingual-alignment-v1"
SUPPORTED_LANGUAGES = {"ar", "en", "ur", "hi", "transliteration"}
ARABIC_SCRIPT_LANGUAGES = {"ar", "ur"}

_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
_SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class LanguageSegment:
    language: str
    text: str


@dataclass(frozen=True)
class TranslationAlignment:
    source_language: str
    target_language: str
    source_text: str
    target_text: str
    evidence_sha256: str
    preserves_citations: bool
    alignment_confidence: float


@dataclass(frozen=True)
class AlignmentDecision:
    decision: str
    reason_code: str
    normalized_source: str
    normalized_target: str
    requires_human_review: bool


def sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def normalize_text(text: str, language: str) -> str:
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError("unsupported language")
    value = unicodedata.normalize("NFKC", text).strip()
    if language in ARABIC_SCRIPT_LANGUAGES:
        value = _ARABIC_DIACRITICS.sub("", value)
        value = value.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه"}))
    value = _SPACE.sub(" ", value)
    return value.casefold()


def script_ratio(text: str, language: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    if language in ARABIC_SCRIPT_LANGUAGES:
        matched = sum("\u0600" <= char <= "\u06ff" for char in letters)
    else:
        matched = sum(("a" <= char.casefold() <= "z") or ("\u0900" <= char <= "\u097f") for char in letters)
    return matched / len(letters)


def validate_alignment(item: TranslationAlignment) -> AlignmentDecision:
    if item.source_language not in SUPPORTED_LANGUAGES or item.target_language not in SUPPORTED_LANGUAGES:
        return AlignmentDecision("blocked", "unsupported_language", "", "", False)
    source = normalize_text(item.source_text, item.source_language)
    target = normalize_text(item.target_text, item.target_language)
    if not source or not target:
        return AlignmentDecision("blocked", "empty_language_segment", source, target, False)
    if sha256_text(item.source_text) != item.evidence_sha256:
        return AlignmentDecision("blocked", "source_evidence_fingerprint_mismatch", source, target, False)
    if item.source_language == item.target_language:
        return AlignmentDecision("blocked", "source_and_target_language_match", source, target, False)
    if not item.preserves_citations:
        return AlignmentDecision("blocked", "translation_lost_claim_citations", source, target, False)
    if not 0 <= item.alignment_confidence <= 1:
        return AlignmentDecision("blocked", "invalid_alignment_confidence", source, target, False)
    if script_ratio(item.target_text, item.target_language) < 0.35:
        return AlignmentDecision("blocked", "target_script_mismatch", source, target, False)
    if item.alignment_confidence < 0.80:
        return AlignmentDecision("review", "low_alignment_confidence", source, target, True)
    if item.target_language in {"ur", "hi", "transliteration"}:
        return AlignmentDecision("review", "human_language_review_required", source, target, True)
    return AlignmentDecision("approved", "alignment_verified", source, target, False)


def require_claim_count_alignment(source_claim_ids: tuple[str, ...], target_claim_ids: tuple[str, ...]) -> None:
    if not source_claim_ids or not target_claim_ids:
        raise ValueError("claim alignment cannot be empty")
    if source_claim_ids != target_claim_ids:
        raise ValueError("translated answer changed claim identity or order")
