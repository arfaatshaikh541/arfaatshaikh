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
    # Only rows whose flag actually differs are written: on a populated database an unconditional rewrite of every chunk takes minutes.
    doc_ids = select(RetrievalDocument.id).where(RetrievalDocument.source_edition_id.in_(edition_ids))
    await db.execute(update(RetrievalChunk).where(RetrievalChunk.document_id.in_(doc_ids), RetrievalChunk.active.is_distinct_from(visible)).values(active=visible))
    await db.execute(update(RetrievalDocument).where(RetrievalDocument.source_edition_id.in_(edition_ids), RetrievalDocument.active.is_distinct_from(visible)).values(active=visible))


async def _apply_target(db: AsyncSession, target: dict, visible: bool) -> tuple[str, int]:
    kind = target["kind"]
    rows: Sequence[Any]
    row: Any
    if kind == "hadith_collection":
        rows = (await db.execute(select(HadithCollection).where(HadithCollection.collection_key == target["key"]))).scalars().all()
        for row in rows:
            row.published = visible
            await db.execute(update(HadithNarration).where(HadithNarration.collection_id == row.id, HadithNarration.published.is_distinct_from(visible)).values(published=visible))
            await _set_retrieval(db, [row.source_edition_id], visible)
        return kind, len(rows)
    if kind == "hadith_translation_edition":
        rows = (await db.execute(select(HadithTranslationEdition).where(HadithTranslationEdition.translation_key == target["key"]))).scalars().all()
        for row in rows:
            row.published = visible
            await db.execute(update(HadithTranslation).where(HadithTranslation.translation_edition_id == row.id, HadithTranslation.published.is_distinct_from(visible)).values(published=visible))
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
            row.published = visible
            await db.execute(update(QuranAyahTranslation).where(QuranAyahTranslation.translation_edition_id == row.id, QuranAyahTranslation.published.is_distinct_from(visible)).values(published=visible))
        await _set_retrieval(db, [r.source_edition_id for r in rows if r.source_edition_id], visible)
        return kind, len(rows)
    if kind == "tafsir_editions":
        stmt = select(TafsirEdition)
        if target.get("keys") is not None:
            stmt = stmt.where(TafsirEdition.edition_key.in_(target["keys"]))
        rows = (await db.execute(stmt)).scalars().all()
        for row in rows:
            row.published = visible
            await db.execute(update(TafsirEntry).where(TafsirEntry.edition_id == row.id, TafsirEntry.published.is_distinct_from(visible)).values(published=visible))
            await db.execute(update(TafsirCollection).where(TafsirCollection.id == row.collection_id).values(published=visible))
        await _set_retrieval(db, [r.source_edition_id for r in rows], visible)
        return kind, len(rows)
    if kind == "tafsir_translation_edition":
        rows = (await db.execute(select(TafsirTranslationEdition).where(TafsirTranslationEdition.translation_key == target["key"]))).scalars().all()
        for row in rows:
            row.published = visible
            await db.execute(update(TafsirTranslation).where(TafsirTranslation.translation_edition_id == row.id, TafsirTranslation.published.is_distinct_from(visible)).values(published=visible))
        await _set_retrieval(db, [r.source_edition_id for r in rows], visible)
        return kind, len(rows)
    raise ValueError(f"unknown target kind {kind}")


async def refresh_dependent_visibility(db: AsyncSession) -> None:
    """Authors are visible only while one of their works is; graph nodes/edges follow their source rows.

    The end state is the same as rewriting everything, but only rows that differ are written, so an administrator's action on a
    populated database takes milliseconds instead of minutes.
    """
    visible_authors = select(TafsirCollection.author_id).where(TafsirCollection.published.is_(True))
    await db.execute(update(TafsirAuthor).where(TafsirAuthor.published.is_(True), TafsirAuthor.id.not_in(visible_authors)).values(published=False))
    await db.execute(update(TafsirAuthor).where(TafsirAuthor.published.is_(False), TafsirAuthor.id.in_(visible_authors)).values(published=True))
    for entity_type, source_ids in (("tafsir_entry", select(TafsirEntry.id).where(TafsirEntry.published.is_(True))),
                                    ("tafsir_work", select(TafsirCollection.id).where(TafsirCollection.published.is_(True))),
                                    ("scholar", select(TafsirAuthor.id).where(TafsirAuthor.published.is_(True)))):
        entity = CanonicalKnowledgeEntity
        await db.execute(update(entity).where(entity.entity_type == entity_type, entity.publication_status == "published", entity.source_entity_id.not_in(source_ids)).values(publication_status="draft"))
        await db.execute(update(entity).where(entity.entity_type == entity_type, entity.publication_status != "published", entity.source_entity_id.in_(source_ids)).values(publication_status="published"))
    hidden = select(CanonicalKnowledgeEntity.id).where(CanonicalKnowledgeEntity.publication_status != "published")
    rel = KnowledgeRelationship
    await db.execute(update(rel).where(rel.published.is_(True), (rel.source_entity_id.in_(hidden)) | (rel.target_entity_id.in_(hidden))).values(published=False))
    await db.execute(update(rel).where(rel.published.is_(False), rel.source_entity_id.not_in(hidden), rel.target_entity_id.not_in(hidden)).values(published=True))


async def apply_manifest_policy(db: AsyncSession, manifest: dict, *, dry_run: bool = False, only: Sequence[str] | None = None) -> list[dict]:
    """Apply the publication decision of every manifest dataset (or only those named in `only`) to the content tables."""
    from app.models.content_contract import DataSet
    datasets = {d.dataset_key: d for d in (await db.scalars(select(DataSet))).all()}
    report: list[dict] = []
    for entry in manifest["datasets"]:
        targets = entry.get("targets") or []
        if not targets or (only is not None and entry["id"] not in only):
            continue
        visible = desired_visibility(datasets.get(entry["id"]))
        touched = []
        for target in targets:
            kind, count = await _apply_target(db, target, visible)
            touched.append({"kind": kind, "rows": count})
        report.append({"dataset": entry["id"], "visible": visible, "targets": touched})
    if report or only is None:  # a dataset without content-table targets (knowledge records, directories) leaves the dependent rows untouched
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
