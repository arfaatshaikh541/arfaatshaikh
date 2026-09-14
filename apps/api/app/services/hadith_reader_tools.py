from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, or_, select

from app.core.errors import AppError
from app.models.hadith import (
    HadithBookmark, HadithBook, HadithChapter, HadithCitationExport, HadithCollection,
    HadithGrading, HadithIsnadNode, HadithNarration, HadithNarrator, HadithNarratorAlias,
    HadithReadingHistory, HadithTranslation,
)


class HadithReaderToolsService:
    def __init__(self, db): self.db = db

    async def _published_narration(self, narration_id: UUID) -> HadithNarration:
        row = await self.db.scalar(select(HadithNarration).where(HadithNarration.id == narration_id, HadithNarration.published.is_(True)))
        if not row: raise AppError("hadith_narration_not_found", "Published hadith narration not found", 404)
        return row

    async def search(self, query: str | None, collection: str | None, grader: str | None, grading: str | None, narrator: str | None, limit: int, offset: int):
        stmt = (select(HadithNarration, HadithCollection, HadithBook, HadithChapter)
                .join(HadithCollection, HadithCollection.id == HadithNarration.collection_id)
                .join(HadithBook, HadithBook.id == HadithNarration.book_id)
                .outerjoin(HadithChapter, HadithChapter.id == HadithNarration.chapter_id)
                .where(HadithNarration.published.is_(True), HadithCollection.published.is_(True)))
        if collection: stmt = stmt.where(HadithCollection.collection_key == collection)
        if query:
            needle = f"%{query.strip()}%"
            stmt = stmt.where(or_(HadithNarration.canonical_reference.ilike(needle), HadithNarration.arabic_matn.ilike(needle)))
        if grader or grading:
            stmt = stmt.join(HadithGrading, HadithGrading.narration_id == HadithNarration.id).where(HadithGrading.published.is_(True))
            if grader: stmt = stmt.where(HadithGrading.grader_name.ilike(f"%{grader.strip()}%"))
            if grading: stmt = stmt.where(HadithGrading.grading_label == grading)
        if narrator:
            stmt = stmt.join(HadithIsnadNode, HadithIsnadNode.narration_id == HadithNarration.id).where(HadithIsnadNode.transmitted_name.ilike(f"%{narrator.strip()}%"))
        rows = (await self.db.execute(stmt.distinct().order_by(HadithCollection.collection_key, HadithNarration.collection_hadith_number).limit(limit).offset(offset))).all()
        out = []
        for n, c, b, ch in rows:
            labels = list((await self.db.scalars(select(HadithGrading.grading_label).where(HadithGrading.narration_id == n.id, HadithGrading.published.is_(True)).distinct().order_by(HadithGrading.grading_label))).all())
            out.append({"id": n.id, "canonical_reference": n.canonical_reference, "collection_key": c.collection_key, "collection_title": c.display_title, "book_number": b.book_number, "chapter_number": ch.chapter_number if ch else None, "arabic_matn": n.arabic_matn, "grading_labels": labels})
        return out

    async def isnad(self, narration_id: UUID):
        await self._published_narration(narration_id)
        rows = list((await self.db.scalars(select(HadithIsnadNode).where(HadithIsnadNode.narration_id == narration_id).order_by(HadithIsnadNode.position))).all())
        return [{"position": r.position, "narrator_id": r.narrator_id, "transmitted_name": r.transmitted_name, "transmission_term": r.transmission_term} for r in rows]

    async def narrator_profile(self, narrator_id: UUID):
        row = await self.db.get(HadithNarrator, narrator_id)
        if not row: raise AppError("hadith_narrator_not_found", "Narrator profile not found", 404)
        aliases = list((await self.db.scalars(select(HadithNarratorAlias.alias).where(HadithNarratorAlias.narrator_id == row.id).order_by(HadithNarratorAlias.alias))).all())
        return {"id": row.id, "canonical_name": row.canonical_name, "arabic_name": row.arabic_name, "disambiguation_note": row.disambiguation_note, "aliases": aliases, "source_passage_id": row.source_passage_id}

    async def list_bookmarks(self, user_id: UUID):
        rows = (await self.db.execute(select(HadithBookmark, HadithNarration).join(HadithNarration, HadithNarration.id == HadithBookmark.narration_id).where(HadithBookmark.user_id == user_id, HadithNarration.published.is_(True)).order_by(HadithBookmark.created_at.desc()))).all()
        return [{"id": b.id, "narration_id": n.id, "canonical_reference": n.canonical_reference, "note": b.note} for b, n in rows]

    async def save_bookmark(self, user_id: UUID, narration_id: UUID, note: str | None):
        narration = await self._published_narration(narration_id)
        row = await self.db.scalar(select(HadithBookmark).where(HadithBookmark.user_id == user_id, HadithBookmark.narration_id == narration.id))
        if row: row.note = note
        else:
            row = HadithBookmark(user_id=user_id, narration_id=narration.id, note=note); self.db.add(row)
        await self.db.flush(); return {"id": row.id, "narration_id": narration.id, "canonical_reference": narration.canonical_reference, "note": row.note}

    async def delete_bookmark(self, user_id: UUID, bookmark_id: UUID):
        row = await self.db.scalar(select(HadithBookmark).where(HadithBookmark.id == bookmark_id, HadithBookmark.user_id == user_id))
        if not row: raise AppError("hadith_bookmark_not_found", "Bookmark not found", 404)
        await self.db.delete(row)

    async def record_history(self, user_id: UUID, narration_id: UUID):
        narration = await self._published_narration(narration_id)
        now = datetime.now(timezone.utc)
        row = await self.db.scalar(select(HadithReadingHistory).where(HadithReadingHistory.user_id == user_id, HadithReadingHistory.narration_id == narration.id))
        if row: row.last_read_at = now; row.read_count += 1
        else:
            row = HadithReadingHistory(user_id=user_id, narration_id=narration.id, last_read_at=now, read_count=1); self.db.add(row)
        await self.db.flush(); return {"narration_id": narration.id, "canonical_reference": narration.canonical_reference, "last_read_at": row.last_read_at, "read_count": row.read_count}

    async def history(self, user_id: UUID, limit: int):
        rows = (await self.db.execute(select(HadithReadingHistory, HadithNarration).join(HadithNarration, HadithNarration.id == HadithReadingHistory.narration_id).where(HadithReadingHistory.user_id == user_id, HadithNarration.published.is_(True)).order_by(HadithReadingHistory.last_read_at.desc()).limit(limit))).all()
        return [{"narration_id": n.id, "canonical_reference": n.canonical_reference, "last_read_at": h.last_read_at, "read_count": h.read_count} for h, n in rows]

    async def citation_export(self, user_id: UUID, narration_id: UUID, format: str):
        narration = await self._published_narration(narration_id)
        collection = await self.db.get(HadithCollection, narration.collection_id)
        data = {"canonical_reference": narration.canonical_reference, "collection": collection.display_title if collection else None, "arabic_matn": narration.arabic_matn}
        if format == "json": payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        elif format == "csv":
            buf = io.StringIO(); writer = csv.DictWriter(buf, fieldnames=list(data)); writer.writeheader(); writer.writerow(data); payload = buf.getvalue()
        else: payload = f"{narration.arabic_matn}\n\n{narration.canonical_reference}"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        row = HadithCitationExport(user_id=user_id, narration_id=narration.id, format=format, payload_sha256=digest, created_at=datetime.now(timezone.utc)); self.db.add(row); await self.db.flush()
        return {"format": format, "payload": payload, "sha256": digest}
