"""One search across every verified entity type. Each result states what it is and where it came from.

Nothing is synthesised: results are rows that exist in published, enabled datasets. A type with no
published data simply returns no results and is reported in `empty_types`, so the UI can say why.
"""
from __future__ import annotations

from typing import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_contract import DataSet, DirectoryListing, KnowledgeRecord, RECORD_TYPES
from app.models.hadith import HadithCollection, HadithNarration, HadithTranslation, HadithTranslationEdition
from app.models.knowledge_graph import KnowledgeTopic
from app.models.learning import Course
from app.models.quran import QuranAyah, QuranAyahTranslation, QuranSurah, QuranTranslationEdition
from app.models.tafsir import TafsirAuthor, TafsirCollection, TafsirEdition, TafsirEntry
from app.services.directory import public_filter
from app.services.retrieval import extract_search_terms

ALL_TYPES = ("quran", "hadith", "tafsir", "topic", "course", "directory", *RECORD_TYPES)
PER_TYPE_LIMIT = 8


def ar_match(column, query: str):
    """Index-backed, diacritic-insensitive word match (see migration 20261001_0085)."""
    return func.to_tsvector("simple", func.woi_ar_norm(column)).op("@@")(func.plainto_tsquery("simple", func.woi_ar_norm(query)))


def snippet(text: str, terms: Sequence[str], width: int = 240) -> str:
    flat = " ".join(text.split())
    lowered = flat.lower()
    positions = [lowered.find(t.lower()) for t in terms if lowered.find(t.lower()) >= 0]
    start = max(min(positions) - 60, 0) if positions else 0
    out = flat[start:start + width]
    return ("…" if start else "") + out + ("…" if start + width < len(flat) else "")


def _item(kind: str, *, title: str, text: str, reference: str, source: str, licence: str | None, path: str, terms: Sequence[str], extra: dict | None = None) -> dict:
    return {"type": kind, "title": title, "snippet": snippet(text, terms), "reference": reference, "source": source,
            "license": licence, "path": path, **(extra or {})}


async def unified_search(db: AsyncSession, q: str, types: Sequence[str] | None = None, limit: int = PER_TYPE_LIMIT) -> dict:
    wanted = [t for t in (types or ALL_TYPES) if t in ALL_TYPES]
    terms = extract_search_terms(q) or [q]
    needle = f"%{q.strip()}%"
    results: list[dict] = []
    empty: list[str] = []

    async def run(kind: str, coro) -> None:
        rows = await coro
        if not rows:
            empty.append(kind)
        results.extend(rows)

    async def quran() -> list[dict]:
        out: list[dict] = []
        ar = (await db.execute(select(QuranAyah, QuranSurah).join(QuranSurah, QuranSurah.id == QuranAyah.surah_id)
                               .where(ar_match(QuranAyah.arabic_text, q)).order_by(QuranSurah.surah_number, QuranAyah.ayah_number).limit(limit))).all()
        for ayah, surah in ar:
            out.append(_item("quran", title=f"Qur'an {ayah.canonical_reference}", text=ayah.arabic_text, reference=ayah.canonical_reference,
                             source="Qur'an, Uthmani text (Hafs)", licence="CC BY 4.0", path=f"/quran/{surah.surah_number}", terms=terms, extra={"language": "ar", "layer": "primary_source"}))
        tr = (await db.execute(select(QuranAyahTranslation, QuranTranslationEdition, QuranAyah, QuranSurah)
                               .join(QuranTranslationEdition, QuranTranslationEdition.id == QuranAyahTranslation.translation_edition_id)
                               .join(QuranAyah, QuranAyah.id == QuranAyahTranslation.ayah_id).join(QuranSurah, QuranSurah.id == QuranAyah.surah_id)
                               .where(QuranAyahTranslation.published.is_(True), QuranTranslationEdition.published.is_(True), QuranAyahTranslation.translated_text.ilike(needle))
                               .order_by(QuranSurah.surah_number, QuranAyah.ayah_number).limit(limit))).all()
        for row, edition, ayah, surah in tr:
            out.append(_item("quran", title=f"Qur'an {ayah.canonical_reference}", text=row.translated_text, reference=ayah.canonical_reference,
                             source=edition.display_name, licence=None, path=f"/quran/{surah.surah_number}", terms=terms, extra={"language": edition.language, "layer": "primary_source"}))
        return out

    async def hadith() -> list[dict]:
        out: list[dict] = []
        rows = (await db.execute(select(HadithNarration, HadithCollection).join(HadithCollection, HadithCollection.id == HadithNarration.collection_id)
                                 .where(HadithNarration.published.is_(True), HadithCollection.published.is_(True), ar_match(HadithNarration.arabic_matn, q)).limit(limit))).all()
        for n, c in rows:
            out.append(_item("hadith", title=f"{c.display_title} {n.collection_hadith_number}", text=n.arabic_matn, reference=n.canonical_reference,
                             source=c.display_title, licence=None, path=f"/hadith/{c.collection_key}", terms=terms, extra={"language": "ar", "layer": "primary_source"}))
        tr = (await db.execute(select(HadithTranslation, HadithTranslationEdition, HadithNarration, HadithCollection)
                               .join(HadithTranslationEdition, HadithTranslationEdition.id == HadithTranslation.translation_edition_id)
                               .join(HadithNarration, HadithNarration.id == HadithTranslation.narration_id).join(HadithCollection, HadithCollection.id == HadithNarration.collection_id)
                               .where(HadithTranslation.published.is_(True), HadithTranslationEdition.published.is_(True), HadithNarration.published.is_(True),
                                      HadithCollection.published.is_(True), HadithTranslation.translated_text.ilike(needle)).limit(limit))).all()
        for t, e, n, c in tr:
            out.append(_item("hadith", title=f"{c.display_title} {n.collection_hadith_number}", text=t.translated_text, reference=n.canonical_reference,
                             source=f"{c.display_title} - {e.translator_name or e.translation_key}", licence=None, path=f"/hadith/{c.collection_key}", terms=terms, extra={"language": e.language, "layer": "primary_source"}))
        return out

    async def tafsir() -> list[dict]:
        rows = (await db.execute(select(TafsirEntry, TafsirEdition, TafsirCollection, TafsirAuthor)
                                 .join(TafsirEdition, TafsirEdition.id == TafsirEntry.edition_id).join(TafsirCollection, TafsirCollection.id == TafsirEdition.collection_id)
                                 .join(TafsirAuthor, TafsirAuthor.id == TafsirCollection.author_id)
                                 .where(TafsirEntry.published.is_(True), TafsirEdition.published.is_(True), TafsirCollection.published.is_(True), TafsirAuthor.published.is_(True),
                                        ar_match(TafsirEntry.arabic_text, q)).order_by(TafsirEntry.surah_number, TafsirEntry.start_ayah_number).limit(limit))).all()
        return [_item("tafsir", title=f"{c.display_title} {e.canonical_reference}", text=e.arabic_text, reference=e.canonical_reference,
                      source=f"{c.display_title} - {a.canonical_name}", licence=None, path=f"/tafsir/{e.surah_number}/{e.start_ayah_number}", terms=terms,
                      extra={"language": ed.language, "layer": "scholarly_explanation"}) for e, ed, c, a in rows]

    async def topics() -> list[dict]:
        rows = (await db.scalars(select(KnowledgeTopic).where(KnowledgeTopic.published.is_(True), or_(KnowledgeTopic.english_name.ilike(needle), KnowledgeTopic.arabic_name.ilike(needle), KnowledgeTopic.description.ilike(needle))).limit(limit))).all()
        return [_item("topic", title=t.english_name, text=t.description or t.arabic_name, reference=t.topic_key, source="World of Islam topic index", licence=None, path="/topics", terms=terms, extra={"layer": "secondary_source"}) for t in rows]

    async def courses() -> list[dict]:
        rows = (await db.scalars(select(Course).where(Course.status == "published", or_(Course.title.ilike(needle), Course.summary.ilike(needle))).limit(limit))).all()
        return [_item("course", title=c.title, text=c.summary, reference=c.slug, source="World of Islam learning", licence=None, path="/learning", terms=terms, extra={"layer": "secondary_source"}) for c in rows]

    async def records(kind: str) -> list[dict]:
        document = func.to_tsvector("simple", KnowledgeRecord.title + " " + func.coalesce(KnowledgeRecord.arabic_title, "") + " " + KnowledgeRecord.description)
        rows = (await db.execute(select(KnowledgeRecord, DataSet).join(DataSet, DataSet.id == KnowledgeRecord.dataset_id)
                                 .where(DataSet.publication_status == "published", DataSet.enabled.is_(True), KnowledgeRecord.entity_type == kind,
                                        document.op("@@")(func.plainto_tsquery("simple", q))).limit(limit))).all()
        return [_item(kind, title=r.title, text=r.description, reference=r.record_key, source=r.source, licence=r.license, path=f"/knowledge/{kind}/{d.dataset_key}/{r.record_key}",
                      terms=terms, extra={"scholarly_status": r.scholarly_status, "confidence": r.confidence, "last_verified": r.last_verified.isoformat() if r.last_verified else None, "layer": "secondary_source"}) for r, d in rows]

    async def directory() -> list[dict]:
        document = func.to_tsvector("simple", DirectoryListing.name + " " + func.coalesce(DirectoryListing.arabic_name, "") + " " + func.coalesce(DirectoryListing.description, "") + " " + func.coalesce(DirectoryListing.city, ""))
        rows = (await db.scalars(select(DirectoryListing).where(public_filter(), document.op("@@")(func.plainto_tsquery("simple", q))).limit(limit))).all()
        return [_item("directory", title=r.name, text=r.description or r.address or r.name, reference=str(r.id), source=r.source, licence=r.license, path=f"/directory/{r.id}", terms=terms,
                      extra={"listing_type": r.listing_type, "verification_status": r.verification_status}) for r in rows]

    for kind in wanted:
        if kind == "quran": await run(kind, quran())
        elif kind == "hadith": await run(kind, hadith())
        elif kind == "tafsir": await run(kind, tafsir())
        elif kind == "topic": await run(kind, topics())
        elif kind == "course": await run(kind, courses())
        elif kind == "directory": await run(kind, directory())
        else: await run(kind, records(kind))
    return {"query": q, "results": results, "empty_types": empty, "searched_types": wanted}
