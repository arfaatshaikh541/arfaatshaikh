"""Applies the manifest's publication decisions to the content tables, so what the public sees always
matches data/source-manifest.json. Idempotent and reversible: it only flips `published` / `active` flags and
never touches the stored text or the source-registry approvals.

A dataset is shown only if the manifest says `published` AND can_publish() agrees (licence status and
validation). Everything else is hidden from readers, search, the assistant and the knowledge graph.
"""
from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hadith import HadithCollection, HadithNarration, HadithTranslation, HadithTranslationEdition
from app.models.knowledge_network import CanonicalKnowledgeEntity, KnowledgeRelationship
from app.models.quran import QuranAyahTranslation, QuranTranslationEdition
from app.models.retrieval import RetrievalChunk, RetrievalDocument
from app.models.tafsir import TafsirAuthor, TafsirCollection, TafsirEdition, TafsirEntry, TafsirTranslation, TafsirTranslationEdition
from app.services.data_contracts import can_publish


def desired_visibility(dataset) -> bool:
    """Visible only if an enabled dataset is published AND its licence/validation state still permits it."""
    if dataset is None or dataset.publication_status != "published" or not dataset.enabled:
        return False
    allowed, _ = can_publish(license_status=dataset.license_status, validation_status=dataset.validation_status, rights_confirmation=dataset.rights_confirmation)
    return allowed


async def _set_retrieval(db: AsyncSession, edition_ids: list, visible: bool) -> None:
    if not edition_ids:
        return
    doc_ids = select(RetrievalDocument.id).where(RetrievalDocument.source_edition_id.in_(edition_ids))
    await db.execute(update(RetrievalChunk).where(RetrievalChunk.document_id.in_(doc_ids)).values(active=visible))
    await db.execute(update(RetrievalDocument).where(RetrievalDocument.source_edition_id.in_(edition_ids)).values(active=visible))


async def _apply_target(db: AsyncSession, target: dict, visible: bool) -> tuple[str, int]:
    kind = target["kind"]
    rows: Sequence[Any]
    row: Any
    if kind == "hadith_collection":
        rows = (await db.execute(select(HadithCollection).where(HadithCollection.collection_key == target["key"]))).scalars().all()
        for row in rows:
            row.published = visible
            await db.execute(update(HadithNarration).where(HadithNarration.collection_id == row.id).values(published=visible))
            await _set_retrieval(db, [row.source_edition_id], visible)
        return kind, len(rows)
    if kind == "hadith_translation_edition":
        rows = (await db.execute(select(HadithTranslationEdition).where(HadithTranslationEdition.translation_key == target["key"]))).scalars().all()
        for row in rows:
            row.published = visible
            await db.execute(update(HadithTranslation).where(HadithTranslation.translation_edition_id == row.id).values(published=visible))
            await _set_retrieval(db, [row.source_edition_id], visible)
        return kind, len(rows)
    if kind in ("quran_translation_edition", "quran_translation_editions"):
        stmt = select(QuranTranslationEdition)
        if kind == "quran_translation_edition":
            stmt = stmt.where(QuranTranslationEdition.translation_key == target["key"])
        elif target.get("all_except"):
            stmt = stmt.where(QuranTranslationEdition.translation_key.not_in(target["all_except"]))
        rows = (await db.execute(stmt)).scalars().all()
        for row in rows:
            if row.published != visible:
                row.published = visible
                await db.execute(update(QuranAyahTranslation).where(QuranAyahTranslation.translation_edition_id == row.id).values(published=visible))
        await _set_retrieval(db, [r.source_edition_id for r in rows if r.source_edition_id], visible)
        return kind, len(rows)
    if kind == "tafsir_editions":
        stmt = select(TafsirEdition)
        if target.get("keys") is not None:
            stmt = stmt.where(TafsirEdition.edition_key.in_(target["keys"]))
        rows = (await db.execute(stmt)).scalars().all()
        for row in rows:
            row.published = visible
            await db.execute(update(TafsirEntry).where(TafsirEntry.edition_id == row.id).values(published=visible))
            await db.execute(update(TafsirCollection).where(TafsirCollection.id == row.collection_id).values(published=visible))
        await _set_retrieval(db, [r.source_edition_id for r in rows], visible)
        return kind, len(rows)
    if kind == "tafsir_translation_edition":
        rows = (await db.execute(select(TafsirTranslationEdition).where(TafsirTranslationEdition.translation_key == target["key"]))).scalars().all()
        for row in rows:
            row.published = visible
            await db.execute(update(TafsirTranslation).where(TafsirTranslation.translation_edition_id == row.id).values(published=visible))
        await _set_retrieval(db, [r.source_edition_id for r in rows], visible)
        return kind, len(rows)
    raise ValueError(f"unknown target kind {kind}")


async def refresh_dependent_visibility(db: AsyncSession) -> None:
    """Authors are visible only while one of their works is; graph nodes/edges follow their source rows."""
    visible_authors = select(TafsirCollection.author_id).where(TafsirCollection.published.is_(True))
    await db.execute(update(TafsirAuthor).values(published=False))
    await db.execute(update(TafsirAuthor).where(TafsirAuthor.id.in_(visible_authors)).values(published=True))
    # graph entities: tafsir entries/works/scholars mirror their rows; a relationship is visible only if both ends are
    await db.execute(update(CanonicalKnowledgeEntity).where(CanonicalKnowledgeEntity.entity_type == "tafsir_entry").values(publication_status="draft"))
    await db.execute(update(CanonicalKnowledgeEntity).where(CanonicalKnowledgeEntity.entity_type == "tafsir_entry",
                                                            CanonicalKnowledgeEntity.source_entity_id.in_(select(TafsirEntry.id).where(TafsirEntry.published.is_(True)))).values(publication_status="published"))
    await db.execute(update(CanonicalKnowledgeEntity).where(CanonicalKnowledgeEntity.entity_type == "tafsir_work").values(publication_status="draft"))
    await db.execute(update(CanonicalKnowledgeEntity).where(CanonicalKnowledgeEntity.entity_type == "tafsir_work",
                                                            CanonicalKnowledgeEntity.source_entity_id.in_(select(TafsirCollection.id).where(TafsirCollection.published.is_(True)))).values(publication_status="published"))
    await db.execute(update(CanonicalKnowledgeEntity).where(CanonicalKnowledgeEntity.entity_type == "scholar").values(publication_status="draft"))
    await db.execute(update(CanonicalKnowledgeEntity).where(CanonicalKnowledgeEntity.entity_type == "scholar",
                                                            CanonicalKnowledgeEntity.source_entity_id.in_(select(TafsirAuthor.id).where(TafsirAuthor.published.is_(True)))).values(publication_status="published"))
    hidden = select(CanonicalKnowledgeEntity.id).where(CanonicalKnowledgeEntity.publication_status != "published")
    await db.execute(update(KnowledgeRelationship).values(published=True))
    await db.execute(update(KnowledgeRelationship).where(KnowledgeRelationship.source_entity_id.in_(hidden)).values(published=False))
    await db.execute(update(KnowledgeRelationship).where(KnowledgeRelationship.target_entity_id.in_(hidden)).values(published=False))


async def apply_manifest_policy(db: AsyncSession, manifest: dict, *, dry_run: bool = False) -> list[dict]:
    from app.models.content_contract import DataSet
    datasets = {d.dataset_key: d for d in (await db.scalars(select(DataSet))).all()}
    report: list[dict] = []
    for entry in manifest["datasets"]:
        targets = entry.get("targets") or []
        if not targets:
            continue
        visible = desired_visibility(datasets.get(entry["id"]))
        touched = []
        for target in targets:
            kind, count = await _apply_target(db, target, visible)
            touched.append({"kind": kind, "rows": count})
        report.append({"dataset": entry["id"], "visible": visible, "targets": touched})
    await refresh_dependent_visibility(db)
    if dry_run:
        await db.rollback()
    return report


async def published_row_count(db: AsyncSession, target: dict) -> int:
    """How many rows of a manifest target are currently visible (used by validation, read-only)."""
    from sqlalchemy import func
    kind = target["kind"]
    if kind == "hadith_collection":
        return await db.scalar(select(func.count()).select_from(HadithCollection).where(HadithCollection.collection_key == target["key"], HadithCollection.published.is_(True))) or 0
    if kind == "hadith_translation_edition":
        return await db.scalar(select(func.count()).select_from(HadithTranslationEdition).where(HadithTranslationEdition.translation_key == target["key"], HadithTranslationEdition.published.is_(True))) or 0
    if kind in ("quran_translation_edition", "quran_translation_editions"):
        stmt = select(func.count()).select_from(QuranTranslationEdition).where(QuranTranslationEdition.published.is_(True))
        if kind == "quran_translation_edition":
            stmt = stmt.where(QuranTranslationEdition.translation_key == target["key"])
        elif target.get("all_except"):
            stmt = stmt.where(QuranTranslationEdition.translation_key.not_in(target["all_except"]))
        return await db.scalar(stmt) or 0
    if kind == "tafsir_editions":
        stmt = select(func.count()).select_from(TafsirEdition).where(TafsirEdition.published.is_(True))
        if target.get("keys") is not None:
            stmt = stmt.where(TafsirEdition.edition_key.in_(target["keys"]))
        return await db.scalar(stmt) or 0
    if kind == "tafsir_translation_edition":
        return await db.scalar(select(func.count()).select_from(TafsirTranslationEdition).where(TafsirTranslationEdition.translation_key == target["key"], TafsirTranslationEdition.published.is_(True))) or 0
    return 0
