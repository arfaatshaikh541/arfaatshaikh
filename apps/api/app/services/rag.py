"""Retrieval-augmented answering, with every step inspectable and nothing generated that is not checkable.

Pipeline:  classify -> retrieve (verified, published, approved evidence only) -> rank -> assess confidence
           -> abstain if the evidence is too weak -> assemble labelled sections -> (optional) AI synthesis that must
           pass citation validation or be discarded.

Answer sections, always distinguished:
    PRIMARY SOURCE          Qur'an and hadith text, quoted verbatim
    SCHOLARLY EXPLANATION   tafsir passages, quoted verbatim and attributed to their author
    SECONDARY SOURCE        anything else that is cited (topics, reference works)
    AI SYNTHESIS            model-written summary; labelled as AI, never a source, and shown only if validated
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Sequence

from app.services.retrieval import EvidenceContract, extract_search_terms

LAYER_BY_CORPUS = {"quran": "primary_source", "hadith": "primary_source", "tafsir": "scholarly_explanation", "topic": "secondary_source", "cross_reference": "secondary_source"}
LAYER_ORDER = ("primary_source", "scholarly_explanation", "secondary_source")
INSUFFICIENT = "Insufficient verified sources."
MIN_COVERAGE = 0.34
MAX_PER_ATTRIBUTION = 3

_RULING_WORDS = re.compile(r"\b(fatwa|haram|halal|forbidden|permissible|obligatory|wajib|mustahabb|makruh|invalid|void)\b", re.I)
_GRADE_WORDS = re.compile(r"\b(sahih|hasan|da['’]?if|weak|authentic|fabricated|mawdu['’]?|munkar|mutawatir)\b", re.I)
_QUOTED = re.compile(r"[﴿“\"«]([^﴾”\"»]{12,})[﴾”\"»]")
_LABEL = re.compile(r"\[(\d{1,3})\]")


_QURAN_KEY = re.compile(r"^(?:[\w\-]+:)?(\d{1,3}):(\d{1,3})$")


def display_reference(evidence: EvidenceContract) -> str:
    """Readable reference for a passage key such as 'eng-mohammedmarmadu:46:35' -> "Qur'an 46:35"."""
    match = _QURAN_KEY.match(evidence.canonical_reference)
    if evidence.corpus_type == "quran" and match:
        return f"Qur'an {match.group(1)}:{match.group(2)}"
    return evidence.canonical_reference


def layer_of(evidence: EvidenceContract) -> str:
    return LAYER_BY_CORPUS.get(evidence.corpus_type, "secondary_source")


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower(), flags=re.UNICODE).split())


def term_coverage(terms: Sequence[str], text: str) -> float:
    if not terms:
        return 0.0
    lowered = text.lower()
    return sum(1 for t in set(terms) if t.lower() in lowered) / len(set(terms))


@dataclass(frozen=True)
class Ranked:
    evidence: EvidenceContract
    score: float
    coverage: float
    layer: str


def rank_evidence(question: str, evidence: Sequence[EvidenceContract], limit: int) -> list[Ranked]:
    """Order evidence by how much of the question each passage covers, with primary sources first on ties.

    Duplicates (same passage) are dropped and no single author/translator may fill more than MAX_PER_ATTRIBUTION slots,
    so one prolific source cannot crowd out the others.
    """
    terms = extract_search_terms(question)
    seen: set[str] = set()
    ranked: list[Ranked] = []
    for item in evidence:
        if item.source_passage_id in seen:
            continue
        seen.add(item.source_passage_id)
        coverage = term_coverage(terms, item.exact_text)
        hits = sum(item.exact_text.lower().count(t.lower()) for t in set(terms)) if terms else 0
        length_penalty = 1.0 / (1.0 + math.log10(max(len(item.exact_text), 10) / 200 + 1))
        layer = layer_of(item)
        layer_bonus = {"primary_source": 0.15, "scholarly_explanation": 0.05}.get(layer, 0.0)
        ranked.append(Ranked(item, coverage * 0.6 + min(hits, 5) * 0.04 + layer_bonus + length_penalty * 0.1, coverage, layer))
    ranked.sort(key=lambda r: (-r.score, LAYER_ORDER.index(r.layer), r.evidence.canonical_reference))
    kept: list[Ranked] = []
    per_source: dict[str, int] = {}
    for r in ranked:
        if per_source.get(r.evidence.attribution, 0) >= MAX_PER_ATTRIBUTION:
            continue
        per_source[r.evidence.attribution] = per_source.get(r.evidence.attribution, 0) + 1
        kept.append(r)
        if len(kept) >= limit:
            break
    return kept


@dataclass(frozen=True)
class Confidence:
    score: float
    level: str
    abstain: bool
    reasons: tuple[str, ...]


def assess_confidence(question: str, ranked: Sequence[Ranked]) -> Confidence:
    """A transparent heuristic, not a probability: how well do verified passages cover what was asked?"""
    if not ranked:
        return Confidence(0.0, "none", True, ("no_approved_evidence",))
    top = ranked[:3]
    coverage = sum(r.coverage for r in top) / len(top)
    layers = {r.layer for r in ranked}
    sources = {r.evidence.attribution for r in ranked}
    score = round(0.55 * coverage + 0.15 * min(len(ranked), 4) / 4 + 0.2 * (1.0 if {"primary_source", "scholarly_explanation"} <= layers else 0.5 if "primary_source" in layers else 0.0)
                  + 0.1 * (1.0 if len(sources) >= 2 else 0.0), 3)
    reasons: list[str] = []
    if coverage < MIN_COVERAGE:
        reasons.append("low_relevance")
    if "primary_source" not in layers and "scholarly_explanation" not in layers:
        reasons.append("no_primary_or_scholarly_source")
    abstain = bool(reasons)
    level = "high" if score >= 0.7 and not abstain else "medium" if score >= 0.45 and not abstain else "low"
    return Confidence(score, level, abstain, tuple(reasons))


def detect_scholarly_views(ranked: Sequence[Ranked]) -> list[dict]:
    """Group scholarly passages that address the same reference but come from different authors.

    This reports that several attributed views exist, and nothing more: it never claims they disagree or ranks them.
    """
    groups: dict[str, dict[str, Ranked]] = {}
    for r in ranked:
        if r.layer == "scholarly_explanation":
            groups.setdefault(r.evidence.canonical_reference, {})[r.evidence.attribution] = r
    return [{"reference": ref, "views": [{"attribution": a, "label_index": None} for a in sorted(items)],
             "note": "Several scholars comment on this reference. Each view is quoted separately and attributed; compare them in full before drawing conclusions."}
            for ref, items in groups.items() if len(items) >= 2]


def build_sections(ranked: Sequence[Ranked]) -> dict[str, list[dict]]:
    sections: dict[str, list[dict]] = {layer: [] for layer in LAYER_ORDER}
    for index, r in enumerate(ranked):
        sections[r.layer].append({
            "label": f"[{index + 1}]", "reference": display_reference(r.evidence), "attribution": r.evidence.attribution, "text": r.evidence.exact_text,
            "source_edition_id": r.evidence.source_edition_id, "source_passage_id": r.evidence.source_passage_id, "text_sha256": r.evidence.text_sha256,
            "license": r.evidence.licence, "relevance": round(r.coverage, 2)})
    return sections


# ------------------------------------------------------------------ AI synthesis (optional, validated)

def build_synthesis_prompt(question: str, ranked: Sequence[Ranked]) -> str:
    sources = "\n\n".join(f"[{i + 1}] ({r.layer.replace('_', ' ')}; {r.evidence.attribution}; {r.evidence.canonical_reference})\n{r.evidence.exact_text}" for i, r in enumerate(ranked))
    return (
        "You summarise ONLY the numbered sources below for a reader of an Islamic knowledge platform.\n"
        "Rules: every sentence must end with one or more source labels such as [1] or [2][3]. "
        "Use only facts present in the cited sources. Do not quote Qur'an or hadith text yourself; refer to the label instead. "
        "Do not give rulings, fatwas, hadith gradings or personal advice. If the sources do not answer the question, reply exactly: "
        f"{INSUFFICIENT}\n\nQuestion: {question}\n\nSources:\n{sources}\n\nSummary:"
    )


@dataclass
class SynthesisCheck:
    ok: bool
    reasons: list[str] = field(default_factory=list)


def validate_synthesis(text: str, ranked: Sequence[Ranked]) -> SynthesisCheck:
    """Reject any synthesis that cites a label that does not exist, quotes text that is not in the cited source,
    or introduces rulings/gradings that the cited sources do not contain."""
    reasons: list[str] = []
    cleaned = text.strip()
    if not cleaned:
        return SynthesisCheck(False, ["empty"])
    if cleaned == INSUFFICIENT:
        return SynthesisCheck(True)
    valid = {f"[{i + 1}]": r for i, r in enumerate(ranked)}
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\[])", cleaned) if s.strip()]
    for sentence in sentences:
        labels = [f"[{n}]" for n in _LABEL.findall(sentence)]
        if not labels:
            reasons.append(f"uncited sentence: {sentence[:60]}")
            continue
        unknown = [label for label in labels if label not in valid]
        if unknown:
            reasons.append(f"cites nonexistent source {unknown[0]}")
            continue
        cited_text = _norm(" ".join(valid[label].evidence.exact_text for label in labels))
        for quoted in _QUOTED.findall(sentence):
            if _norm(quoted) not in cited_text:
                reasons.append(f"quotation not found in cited source: {quoted[:50]}")
        for pattern, name in ((_RULING_WORDS, "ruling"), (_GRADE_WORDS, "grading")):
            for match in pattern.finditer(sentence):
                if match.group(0).lower() not in cited_text:
                    reasons.append(f"{name} term '{match.group(0)}' is not in the cited sources")
    return SynthesisCheck(not reasons, reasons)
