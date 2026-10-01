"""Sourced knowledge records for the assistant: fiqh, aqeedah, seerah, hadith grading, terminology, library, history, scholars.

Only records of enabled, published datasets are considered. Each hit is returned with the metadata a reader needs to judge it
(work, edition, page, licence, madhhab or school, grader) and is labelled [K1], [K2] ... so it can be cited. The rules are:

 - different madhhabs, schools or graders stay separate entries; the answer never merges, ranks or reconciles them;
 - uncertainty is stated, not hidden (a seerah report that is not 'established', graders whose grades differ, an unreviewed record);
 - nothing is written here: the text shown is the record's own description and structured fields;
 - when no published record matches, nothing is returned and the assistant says so rather than inventing a source.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_contract import DataSet, KnowledgeRecord
from app.services.retrieval import extract_search_terms

SOURCED_KINDS = ("fiqh", "aqeedah", "seerah", "hadith_grading", "terminology", "library_work", "history", "civilization", "scholar")
MIN_COVERAGE = 0.5


@dataclass(frozen=True)
class KnowledgeHit:
    label: str
    record_key: str
    dataset: str
    kind: str
    title: str
    text: str
    source: str
    source_work: str | None
    locator: str
    license: str
    position: str | None  # madhhab, school or None
    scholarly_status: str
    uncertainty: tuple[str, ...]
    coverage: float


def coverage(terms: Sequence[str], text: str) -> float:
    unique = {t.lower() for t in terms}
    if not unique:
        return 0.0
    lowered = text.lower()
    return sum(1 for t in unique if t in lowered) / len(unique)


def uncertainty_of(kind: str, status: str, attributes: dict) -> tuple[str, ...]:
    notes: list[str] = []
    if status in {"unreviewed", "disputed"}:
        notes.append(f"scholarly status: {status}")
    if kind == "seerah" and attributes.get("reliability") not in (None, "established"):
        notes.append(f"report is {str(attributes.get('reliability')).replace('_', ' ')}")
    if kind == "hadith_grading":
        grades = attributes.get("grades") or []
        if len({g.get("grade") for g in grades}) > 1:
            notes.append("graders' grades differ; each is listed separately")
    if kind in {"fiqh", "aqeedah"}:
        notes.append("this is one scholarly position, not the only one")
    return tuple(notes)


def render_text(record: KnowledgeRecord) -> str:
    """The record's own words and fields; nothing is added."""
    a = record.attributes or {}
    parts = [record.description]
    for key in ("question", "ruling", "statement", "reasoning"):
        if a.get(key):
            parts.append(f"{key.capitalize()}: {a[key]}")
    for grade in a.get("grades") or []:
        parts.append(f"{grade['grader']}: {grade['grade']} (source: {grade['grading_source']})")
    return "\n".join(parts)


def locator_of(record: KnowledgeRecord) -> str:
    bits = [record.edition, f"vol. {record.volume}" if record.volume else None, record.chapter, f"p. {record.page}" if record.page else None]
    return ", ".join(b for b in bits if b) or "no locator recorded"


async def search_knowledge(db: AsyncSession, question: str, limit: int = 6) -> list[KnowledgeHit]:
    terms = extract_search_terms(question)
    if not terms:
        return []
    match = or_(*(func.lower(KnowledgeRecord.title + " " + KnowledgeRecord.description).like(f"%{t.lower()}%") for t in terms))
    rows = (await db.execute(
        select(KnowledgeRecord, DataSet).join(DataSet, DataSet.id == KnowledgeRecord.dataset_id)
        .where(DataSet.publication_status == "published", DataSet.enabled.is_(True), KnowledgeRecord.entity_type.in_(SOURCED_KINDS),
               KnowledgeRecord.scholarly_status != "rejected", match).limit(limit * 10))).all()
    scored = []
    for record, dataset in rows:
        score = coverage(terms, f"{record.title} {record.description}")
        if score >= MIN_COVERAGE:
            scored.append((score, record, dataset))
    scored.sort(key=lambda item: (-item[0], item[1].record_key))
    hits = []
    for index, (score, record, dataset) in enumerate(scored[:limit]):
        a = record.attributes or {}
        hits.append(KnowledgeHit(
            label=f"[K{index + 1}]", record_key=record.record_key, dataset=dataset.dataset_key, kind=record.entity_type, title=record.title,
            text=render_text(record), source=record.source, source_work=record.source_work, locator=locator_of(record), license=record.license,
            position=a.get("madhhab") or a.get("school"), scholarly_status=record.scholarly_status,
            uncertainty=uncertainty_of(record.entity_type, record.scholarly_status, a), coverage=round(score, 2)))
    return hits


def hits_view(hits: Sequence[KnowledgeHit]) -> list[dict]:
    return [{"label": h.label, "kind": h.kind, "title": h.title, "text": h.text, "position": h.position, "source": h.source, "source_work": h.source_work,
             "locator": h.locator, "license": h.license, "scholarly_status": h.scholarly_status, "uncertainty": list(h.uncertainty),
             "record": {"dataset": h.dataset, "id": h.record_key}, "relevance": h.coverage} for h in hits]
