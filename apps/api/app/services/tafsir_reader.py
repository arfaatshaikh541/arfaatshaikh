from __future__ import annotations
from uuid import UUID
from sqlalchemy import delete, select
from app.core.errors import AppError
from app.models.knowledge_graph import KnowledgeCrossReference
from app.models.tafsir import (
    TafsirAuthor, TafsirBookmark, TafsirCollection, TafsirEdition, TafsirEntry,
    TafsirStudyCollection, TafsirStudyCollectionItem, TafsirStudyNote,
    TafsirStudyProgress, TafsirTranslation, TafsirTranslationEdition,
)

class TafsirReaderService:
    def __init__(self, db): self.db = db

    async def _published_entry(self, entry_id: UUID):
        entry = await self.db.get(TafsirEntry, entry_id)
        if not entry or not entry.published:
            raise AppError("tafsir_entry_unavailable", "Tafsir entry not found or unpublished", 404)
        edition = await self.db.get(TafsirEdition, entry.edition_id)
        if not edition or not edition.published:
            raise AppError("tafsir_edition_unavailable", "Tafsir edition is not published", 404)
        return entry, edition

    async def reading_payload(self, surah_number: int, ayah_number: int, edition_key: str | None, translation_key: str | None):
        stmt = select(TafsirEntry, TafsirEdition, TafsirCollection, TafsirAuthor).join(TafsirEdition, TafsirEdition.id == TafsirEntry.edition_id).join(TafsirCollection, TafsirCollection.id == TafsirEdition.collection_id).join(TafsirAuthor, TafsirAuthor.id == TafsirCollection.author_id).where(
            TafsirEntry.published.is_(True), TafsirEdition.published.is_(True), TafsirCollection.published.is_(True), TafsirAuthor.published.is_(True),
            TafsirEntry.surah_number == surah_number,
            (TafsirEntry.start_ayah_number.is_(None) | (TafsirEntry.start_ayah_number <= ayah_number)),
            (TafsirEntry.end_ayah_number.is_(None) | (TafsirEntry.end_ayah_number >= ayah_number)),
        )
        if edition_key: stmt = stmt.where(TafsirEdition.edition_key == edition_key)
        rows = (await self.db.execute(stmt.order_by(TafsirCollection.display_title, TafsirEntry.canonical_reference))).all()
        payload=[]
        for entry, edition, collection, author in rows:
            translation=None; translation_edition=None
            if translation_key:
                pair = (await self.db.execute(select(TafsirTranslation, TafsirTranslationEdition).join(TafsirTranslationEdition, TafsirTranslationEdition.id == TafsirTranslation.translation_edition_id).where(
                    TafsirTranslation.tafsir_entry_id == entry.id, TafsirTranslation.published.is_(True),
                    TafsirTranslationEdition.translation_key == translation_key, TafsirTranslationEdition.published.is_(True)
                ))).first()
                if pair: translation, translation_edition = pair
            refs=list((await self.db.scalars(select(KnowledgeCrossReference).where(KnowledgeCrossReference.published.is_(True), ((KnowledgeCrossReference.source_type == "tafsir_entry") & (KnowledgeCrossReference.source_entity_id == entry.id)) | ((KnowledgeCrossReference.target_type == "tafsir_entry") & (KnowledgeCrossReference.target_entity_id == entry.id))))).all())
            payload.append({"entry":entry,"edition":edition,"collection":collection,"author":author,"translation":translation,"translation_edition":translation_edition,"references":refs})
        return payload

    async def bookmarks(self, user_id: UUID):
        return list((await self.db.scalars(select(TafsirBookmark).where(TafsirBookmark.user_id == user_id).order_by(TafsirBookmark.created_at.desc()))).all())
    async def save_bookmark(self, user_id: UUID, payload):
        await self._published_entry(payload.tafsir_entry_id)
        row=await self.db.scalar(select(TafsirBookmark).where(TafsirBookmark.user_id==user_id,TafsirBookmark.tafsir_entry_id==payload.tafsir_entry_id))
        if row: row.note=payload.note
        else: row=TafsirBookmark(user_id=user_id,**payload.model_dump()); self.db.add(row)
        await self.db.flush(); return row
    async def delete_bookmark(self,user_id:UUID,bookmark_id:UUID):
        row=await self.db.get(TafsirBookmark,bookmark_id)
        if not row or row.user_id!=user_id: raise AppError("tafsir_bookmark_not_found","Bookmark not found",404)
        await self.db.delete(row)

    async def notes(self,user_id:UUID): return list((await self.db.scalars(select(TafsirStudyNote).where(TafsirStudyNote.user_id==user_id).order_by(TafsirStudyNote.updated_at.desc()))).all())
    async def create_note(self,user_id:UUID,payload):
        await self._published_entry(payload.tafsir_entry_id); row=TafsirStudyNote(user_id=user_id,**payload.model_dump()); self.db.add(row); await self.db.flush(); return row
    async def delete_note(self,user_id:UUID,note_id:UUID):
        row=await self.db.get(TafsirStudyNote,note_id)
        if not row or row.user_id!=user_id: raise AppError("tafsir_note_not_found","Study note not found",404)
        await self.db.delete(row)

    async def collections(self,user_id:UUID): return list((await self.db.scalars(select(TafsirStudyCollection).where(TafsirStudyCollection.user_id==user_id).order_by(TafsirStudyCollection.name))).all())
    async def create_collection(self,user_id:UUID,payload):
        row=TafsirStudyCollection(user_id=user_id,**payload.model_dump()); self.db.add(row); await self.db.flush(); return row
    async def add_collection_item(self,user_id:UUID,collection_id:UUID,payload):
        collection=await self.db.get(TafsirStudyCollection,collection_id)
        if not collection or collection.user_id!=user_id: raise AppError("tafsir_collection_not_found","Study collection not found",404)
        await self._published_entry(payload.tafsir_entry_id)
        row=TafsirStudyCollectionItem(collection_id=collection_id,**payload.model_dump()); self.db.add(row); await self.db.flush(); return row

    async def progress(self,user_id:UUID): return list((await self.db.scalars(select(TafsirStudyProgress).where(TafsirStudyProgress.user_id==user_id).order_by(TafsirStudyProgress.updated_at.desc()))).all())
    async def save_progress(self,user_id:UUID,payload):
        await self._published_entry(payload.tafsir_entry_id)
        row=await self.db.scalar(select(TafsirStudyProgress).where(TafsirStudyProgress.user_id==user_id,TafsirStudyProgress.tafsir_entry_id==payload.tafsir_entry_id))
        if row: row.status=payload.status; row.progress_percent=payload.progress_percent
        else: row=TafsirStudyProgress(user_id=user_id,**payload.model_dump()); self.db.add(row)
        await self.db.flush(); return row
