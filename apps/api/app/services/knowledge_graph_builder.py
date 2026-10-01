"""Materialise the knowledge graph from published, source-backed data. Every edge cites an evidence passage.

Idempotent: entities are keyed by canonical_key and edges by (source, target, type, evidence), so running
it again only adds what is new and never invents a relationship that no source states:

    ayah  -part_of-> surah                   evidence: the ayah's own source passage (its reference names the surah)
    scholar -authored-> tafsir work          evidence: the author passage stored with the edition
    ayah  -explained_by-> tafsir entry       evidence: the entry's own source passage
"""
from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_network import CanonicalKnowledgeEntity, KnowledgeRelationship
from app.models.quran import QuranAyah, QuranSurah
from app.models.tafsir import TafsirAuthor, TafsirCollection, TafsirEdition, TafsirEntry

CHUNK = 5000


def _slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in text.lower()).strip("-")


async def _bulk(db: AsyncSession, model, rows: list[dict], conflict: list[str]) -> None:
    if not rows:
        return
    size = max(1, min(CHUNK, 30000 // len(rows[0])))  # asyncpg allows at most 32767 bind parameters per statement
    for start in range(0, len(rows), size):
        stmt = pg_insert(model).values(rows[start:start + size]).on_conflict_do_nothing(index_elements=conflict)
        await db.execute(stmt)


async def build_core_graph(db: AsyncSession) -> dict[str, int]:
    from datetime import UTC, datetime
    now = datetime.now(UTC)

    def entity(kind: str, key: str, source_id, en: str, ar: str, url: str, passage_id=None, summary: str = "") -> dict:
        return {"id": uuid4(), "canonical_key": key, "entity_type": kind, "source_entity_id": source_id, "english_label": en[:320], "arabic_label": ar[:320],
                "transliteration": "", "summary": summary, "canonical_url": url, "publication_status": "published", "source_passage_id": passage_id,
                "search_document": {}, "created_at": now, "updated_at": now}

    entities: list[dict] = []
    surahs = (await db.execute(select(QuranSurah))).scalars().all()
    for s in surahs:
        entities.append(entity("quran_surah", f"surah:{s.surah_number}", s.id, s.english_name, s.arabic_name, f"/quran/{s.surah_number}", s.metadata_source_passage_id))
    ayahs = (await db.execute(select(QuranAyah, QuranSurah).join(QuranSurah, QuranSurah.id == QuranAyah.surah_id))).all()
    for a, s in ayahs:
        entities.append(entity("quran_ayah", f"quran:{a.canonical_reference}", a.id, f"Qur'an {a.canonical_reference}", f"{s.arabic_name} {a.ayah_number}", f"/quran/{s.surah_number}", a.source_passage_id))
    authors = (await db.execute(select(TafsirAuthor).where(TafsirAuthor.published.is_(True)))).scalars().all()
    for au in authors:
        if au.source_passage_id:
            entities.append(entity("scholar", f"scholar:{_slug(au.canonical_name)}", au.id, au.canonical_name, au.arabic_name or "", "/tafsir/study", au.source_passage_id))
    works = (await db.execute(select(TafsirCollection, TafsirAuthor).join(TafsirAuthor, TafsirAuthor.id == TafsirCollection.author_id)
                              .where(TafsirCollection.published.is_(True), TafsirAuthor.published.is_(True)))).all()
    for c, au in works:
        entities.append(entity("tafsir_work", f"tafsir-work:{c.collection_key}", c.id, c.display_title, c.arabic_title, "/tafsir/study", au.source_passage_id))
    await _bulk(db, CanonicalKnowledgeEntity, entities, ["canonical_key"])

    ids = {key: id_ for key, id_ in (await db.execute(select(CanonicalKnowledgeEntity.canonical_key, CanonicalKnowledgeEntity.id))).all()}
    rels: list[dict] = []

    def edge(src: str, dst: str, kind: str, evidence, rationale: str, confidence: int = 100) -> None:
        if src in ids and dst in ids and evidence is not None:
            rels.append({"id": uuid4(), "source_entity_id": ids[src], "target_entity_id": ids[dst], "relationship_type": kind, "evidence_passage_id": evidence,
                         "rationale": rationale, "confidence": confidence, "review_status": "approved", "published": True, "created_at": now, "updated_at": now})

    for a, s in ayahs:
        edge(f"quran:{a.canonical_reference}", f"surah:{s.surah_number}", "part_of", a.source_passage_id, f"Ayah {a.canonical_reference} belongs to surah {s.surah_number} in the published Qur'an text (the ayah's own reference).")
    for c, au in works:
        edge(f"scholar:{_slug(au.canonical_name)}", f"tafsir-work:{c.collection_key}", "authored", au.source_passage_id, f"{au.canonical_name} is recorded as the author of {c.display_title}.")
    await _bulk(db, KnowledgeRelationship, rels, ["source_entity_id", "target_entity_id", "relationship_type", "evidence_passage_id"])

    # tafsir entries and their ayah links, edition by edition so memory stays bounded
    entry_entities = entry_edges = 0
    editions = (await db.execute(select(TafsirEdition, TafsirCollection).join(TafsirCollection, TafsirCollection.id == TafsirEdition.collection_id)
                                 .where(TafsirEdition.published.is_(True), TafsirCollection.published.is_(True)))).all()
    for ed, col in editions:
        entries = (await db.scalars(select(TafsirEntry).where(TafsirEntry.edition_id == ed.id, TafsirEntry.published.is_(True)))).all()
        rows = [entity("tafsir_entry", f"tafsir:{ed.edition_key}:{e.canonical_reference}", e.id, f"{col.display_title} {e.canonical_reference}", "", f"/tafsir/{e.surah_number}/{e.start_ayah_number}", e.source_passage_id) for e in entries]
        await _bulk(db, CanonicalKnowledgeEntity, rows, ["canonical_key"])
        entry_entities += len(rows)
        keys = [r["canonical_key"] for r in rows]
        have = {k: i for k, i in (await db.execute(select(CanonicalKnowledgeEntity.canonical_key, CanonicalKnowledgeEntity.id).where(CanonicalKnowledgeEntity.canonical_key.in_(keys)))).all()} if keys else {}
        ids.update(have)
        edges: list[dict] = []
        for e in entries:
            key = f"tafsir:{ed.edition_key}:{e.canonical_reference}"
            for ayah in range(int(e.start_ayah_number or 0), int(e.end_ayah_number or 0) + 1):
                src = f"quran:{e.surah_number}:{ayah}"
                if src in ids and key in ids:
                    edges.append({"id": uuid4(), "source_entity_id": ids[src], "target_entity_id": ids[key], "relationship_type": "explained_by", "evidence_passage_id": e.source_passage_id,
                                  "rationale": f"{col.display_title} attaches this commentary to {e.surah_number}:{ayah} in the published edition.", "confidence": 90, "review_status": "approved",
                                  "published": True, "created_at": now, "updated_at": now})
        await _bulk(db, KnowledgeRelationship, edges, ["source_entity_id", "target_entity_id", "relationship_type", "evidence_passage_id"])
        entry_edges += len(edges)
    await db.flush()
    return {"entities": await db.scalar(select(func.count()).select_from(CanonicalKnowledgeEntity)) or 0,
            "relationships": await db.scalar(select(func.count()).select_from(KnowledgeRelationship)) or 0,
            "entry_entities_seen": entry_entities, "entry_edges_seen": entry_edges}
