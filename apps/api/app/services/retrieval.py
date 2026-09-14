from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING, Iterable, Sequence

from sqlalchemy import or_, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

POLICY_VERSION = "retrieval-v1"
ALLOWED_CORPORA = frozenset({"quran", "hadith", "tafsir", "topic", "cross_reference"})

_STOPWORDS = frozenset({
    "the", "a", "an", "of", "in", "on", "to", "for", "and", "or", "is", "are", "was", "were",
    "what", "why", "how", "who", "whom", "when", "where", "which", "does", "do", "did",
    "say", "says", "said", "about", "with", "that", "this", "these", "those", "it", "its",
    "be", "been", "being", "can", "could", "should", "would", "will", "shall", "teach",
    "teaching", "teachings", "islam", "islamic", "quran", "hadith",
})


def extract_search_terms(question: str) -> list[str]:
    """Pull the significant keywords out of a natural-language question.

    search_evidence() matches real source text against these terms rather than the
    whole question, since a full sentence almost never appears verbatim inside a
    short ayah or hadith translation. Terms are still matched as exact substrings -
    this never invents or paraphrases anything, it only finds where to look.
    """
    words = re.findall(r"[A-Za-z؀-ۿ]+", question)
    terms = [w for w in words if len(w) >= 3 and w.lower() not in _STOPWORDS]
    return terms or [w for w in words if len(w) >= 3]


@dataclass(frozen=True)
class EvidenceContract:
    chunk_id: str
    document_id: str
    corpus_type: str
    canonical_reference: str
    source_edition_id: str
    source_passage_id: str
    exact_text: str
    text_sha256: str
    attribution: str
    licence: str


@dataclass(frozen=True)
class ChunkDraft:
    index: int
    text: str
    start_offset: int
    end_offset: int
    token_estimate: int
    boundary_type: str
    text_sha256: str


def sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def validate_projection_eligibility(*, published: bool, source_approved: bool, ingestion_ready: bool,
                                    retrieval_approved: bool, passage_current: bool, attribution_present: bool,
                                    redistribution_allowed: bool) -> tuple[bool, tuple[str, ...]]:
    checks = {
        "content_unpublished": published,
        "source_not_approved": source_approved,
        "source_not_ready": ingestion_ready,
        "retrieval_not_approved": retrieval_approved,
        "passage_not_current": passage_current,
        "attribution_missing": attribution_present,
        "redistribution_not_allowed": redistribution_allowed,
    }
    failures = tuple(code for code, passed in checks.items() if not passed)
    return not failures, failures


def chunk_exact_text(text: str, *, max_chars: int = 1200) -> list[ChunkDraft]:
    if not text or not text.strip():
        raise ValueError("retrieval text cannot be empty")
    if max_chars < 200:
        raise ValueError("max_chars must be at least 200")
    chunks: list[ChunkDraft] = []
    start = 0
    index = 0
    while start < len(text):
        hard_end = min(start + max_chars, len(text))
        end = hard_end
        boundary = "document_end" if hard_end == len(text) else "hard_limit"
        if hard_end < len(text):
            candidates = [text.rfind("\n\n", start, hard_end), text.rfind("\n", start, hard_end), text.rfind(". ", start, hard_end)]
            best = max(candidates)
            if best > start + max_chars // 2:
                end = best + (2 if text[best:best+2] == ". " else 1)
                boundary = "semantic"
        exact = text[start:end]
        chunks.append(ChunkDraft(index, exact, start, end, max(1, (len(exact) + 3) // 4), boundary, sha256_text(exact)))
        index += 1
        start = end
    return chunks


def validate_evidence_contract(evidence: EvidenceContract) -> None:
    if evidence.corpus_type not in ALLOWED_CORPORA:
        raise ValueError("unsupported corpus type")
    if sha256_text(evidence.exact_text) != evidence.text_sha256:
        raise ValueError("evidence checksum mismatch")
    if not evidence.canonical_reference.strip() or not evidence.attribution.strip() or not evidence.licence.strip():
        raise ValueError("evidence attribution contract incomplete")


def filter_active_candidates(candidates: Iterable[dict]) -> list[dict]:
    """Fail closed: only active document+chunk pairs with current source approval survive."""
    return [c for c in candidates if all((c.get("document_active"), c.get("chunk_active"), c.get("source_approved"), c.get("passage_current"), c.get("retrieval_approved")))]


async def search_evidence(db: "AsyncSession", corpora: Sequence[str], query: str, limit: int) -> list[EvidenceContract]:
    """Shared evidence search used by the retrieval API and the grounded assistant.

    Only approved, ingestion-ready, current source material is returned; the same
    fail-closed predicate backs both /retrieval/query and /assistant/query so the
    assistant can never surface evidence the retrieval API itself would withhold.
    """
    from app.models.retrieval import RetrievalChunk, RetrievalDocument
    from app.models.sources import SourceEdition, SourcePassage

    allowed = set(corpora) & ALLOWED_CORPORA
    if not allowed:
        return []
    terms = extract_search_terms(query)
    if not terms:
        return []
    term_match = or_(*(RetrievalChunk.text.ilike(f"%{term}%") for term in terms))
    stmt = (
        select(RetrievalChunk, RetrievalDocument)
        .join(RetrievalDocument, RetrievalDocument.id == RetrievalChunk.document_id)
        .join(SourceEdition, SourceEdition.id == RetrievalDocument.source_edition_id)
        .join(SourcePassage, SourcePassage.id == RetrievalDocument.source_passage_id)
        .where(
            RetrievalChunk.active.is_(True), RetrievalDocument.active.is_(True),
            RetrievalDocument.corpus_type.in_(allowed), term_match,
            SourceEdition.review_status == "approved", SourceEdition.ingestion_status == "ready",
            SourceEdition.approved_for_retrieval.is_(True), SourcePassage.is_current.is_(True),
            SourcePassage.edition_id == RetrievalDocument.source_edition_id,
        )
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [
        EvidenceContract(
            chunk_id=str(chunk.id), document_id=str(doc.id), corpus_type=doc.corpus_type,
            canonical_reference=doc.canonical_reference, source_edition_id=str(doc.source_edition_id),
            source_passage_id=str(doc.source_passage_id), exact_text=chunk.text, text_sha256=chunk.text_sha256,
            attribution=doc.attribution_snapshot, licence=doc.licence_snapshot,
        )
        for chunk, doc in rows
    ]
