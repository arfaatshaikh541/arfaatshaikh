"""Publish Sahih Muslim into the Hadith reader tables (collection, books, chapters, narrations, English translation).

Run after scripts/import_real_evidence.py. Adds an Arabic source edition (governed
exactly like the English one: acquisition, checksum, review, attribution,
retrieval eligibility) and links every book/chapter/narration to its source passage.

The source package groups hadith into 57 books ("kutub") and has no finer chapter
division, so each book contains a single chapter carrying the book's title. Hadith
numbers are the source package's own sequential numbers.

    uv run python scripts/import_hadith_reader.py
"""
from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import import_real_evidence as base  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.models.hadith import (  # noqa: E402
    HadithBook, HadithChapter, HadithCollection, HadithNarration, HadithTranslation, HadithTranslationEdition,
)
from app.models.sources import Source, SourceEdition, SourcePassage  # noqa: E402
from app.schemas.sources import (  # noqa: E402
    AcquisitionCreate, AttributionUpsert, EditionCreate, IngestionTransition, ReviewAssignmentCreate, ReviewDecisionCreate,
)
from app.services.sources import SourceRegistryService  # noqa: E402



def clean(text: str) -> str:
    return " ".join(text.split())


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def publish(cfg: dict) -> None:
    COLLECTION_KEY = cfg["key"]
    stem = cfg.get("edition_stem") or ("sahih-muslim" if COLLECTION_KEY == "muslim" else "sahih-bukhari")
    arabic_only = bool(cfg.get("arabic_only"))
    AR_EDITION_KEY = f"{stem}-ar"
    data = json.load(gzip.open(cfg["data"], "rt", encoding="utf-8"))
    db = Database(get_settings())
    async with db.session_factory() as session:
        source = await session.scalar(select(Source).where(Source.canonical_title == cfg["title"]))
        en_edition = await session.scalar(select(SourceEdition).where(SourceEdition.edition_key == (AR_EDITION_KEY if arabic_only else f"{stem}-en")))
        if source is None or en_edition is None:
            raise SystemExit("Run scripts/import_real_evidence.py first.")
        if await session.scalar(select(HadithCollection.id).where(HadithCollection.collection_key == COLLECTION_KEY)):
            print("Hadith reader already published, skipping.")
            return
        actor = await base.get_or_create_operator(session)
        registry = SourceRegistryService(session)

        if arabic_only:
            ar_edition = en_edition
        else:
            # Arabic edition, governed like the English one.
            ar_edition = await registry.create_edition(source.id, EditionCreate(
                licence_id=en_edition.licence_id, edition_key=AR_EDITION_KEY, language="ar",
                publisher=f"{cfg['package'].split()[0]} PyPI package", citation_format=f"{cfg['title']}, Hadith {{id}} (Arabic)"))
            wheel_digest, size = base.sha256_file(cfg["wheel"])
            await registry.record_acquisition(ar_edition.id, AcquisitionCreate(
                method="manual_upload", acquired_from=f"Package: {cfg['package']} ({cfg['pypi']})",
                acquired_at=datetime.now(UTC), evidence_reference=f"sha256:{wheel_digest}"), actor)
            await registry.verify_integrity(ar_edition.id, cfg["wheel"].name, "sha256", actor, wheel_digest, size)
            await registry.transition_ingestion(ar_edition.id, IngestionTransition(
                status="validating", rationale="Arabic passages are being loaded from the verified package."), actor)
            assignment = await registry.assign_review(ar_edition.id, ReviewAssignmentCreate(
                reviewer_user_id=actor.id, review_domain="content_accuracy"), actor)
            await registry.submit_review(assignment.id, ReviewDecisionCreate(
                decision="approved",
                rationale="Arabic text comes from the same checksum-verified package and hadith ids as the reviewed English edition."), actor)
            await registry.upsert_attribution(ar_edition.id, AttributionUpsert(
                language="ar", display_text=f"{cfg['title_ar']}. النص العربي من حزمة {cfg['package'].split()[0]}.",
                source_url=cfg["pypi"]))

        books = [c for c in data["chapters"]]
        book_number = {c["id"]: (c["id"] if c["id"] > 0 else max(x["id"] for x in books) + 1) for c in books}
        rows = []  # (key, locator, label, content)
        for c in books:
            n = book_number[c["id"]]
            rows.append((f"{COLLECTION_KEY}{'' if arabic_only else '-ar'}:book:{n}", f"book {n}", f"{cfg['title']}, {c['english']}", c["arabic"]))
        for h in data["hadiths"]:
            if h["arabic"].strip():
                rows.append((f"{COLLECTION_KEY}{'' if arabic_only else '-ar'}:{h['id']}", f"hadith id {h['id']}", f"{cfg['title']}, Hadith {h['id']} (Arabic)", clean(h["arabic"])))
        if arabic_only:
            rows = [r for r in rows if ":book:" in r[0]]
            for i, r_ in enumerate(rows):
                rows[i] = (r_[0].replace(f"{COLLECTION_KEY}-ar:book:", f"{COLLECTION_KEY}:book:"),) + r_[1:]
        passages = base.bulk_add_passages(session, ar_edition, actor, rows)
        await session.flush()
        if not arabic_only:
            await registry.transition_ingestion(ar_edition.id, IngestionTransition(
                status="ready", rationale=f"All {len(passages)} Arabic passages loaded."), actor)
            eligibility = await registry.evaluate_retrieval(ar_edition.id, actor)
            if not eligibility.eligible:
                raise SystemExit(f"Arabic edition not eligible: {eligibility.failed_gates()}")
        by_key = {p.passage_key: p for p in passages}
        if arabic_only:
            for p in await session.scalars(select(SourcePassage).where(SourcePassage.edition_id == ar_edition.id, SourcePassage.is_current.is_(True))):
                by_key.setdefault(p.passage_key, p)

        en_by_key = {p.passage_key: p for p in await session.scalars(
            select(SourcePassage).where(SourcePassage.edition_id == en_edition.id, SourcePassage.is_current.is_(True)))}

        collection = HadithCollection(
            source_edition_id=ar_edition.id, collection_key=COLLECTION_KEY, arabic_title=cfg["title_ar"],
            display_title=cfg["title"], compiler_name=cfg["compiler"], language="ar", published=True)
        session.add(collection)
        await session.flush()

        book_rows, chapter_rows = {}, {}
        for c in books:
            n = book_number[c["id"]]
            passage = by_key[f"{COLLECTION_KEY}{'' if arabic_only else '-ar'}:book:{n}"]
            book = HadithBook(collection_id=collection.id, book_number=n, arabic_title=c["arabic"],
                              display_title=c["english"], source_passage_id=passage.id, published=True)
            session.add(book)
            book_rows[c["id"]] = (book, c, passage)
        await session.flush()
        for cid, (book, c, passage) in book_rows.items():
            chapter = HadithChapter(book_id=book.id, chapter_number=1, arabic_title=c["arabic"],
                                    display_title=c["english"], source_passage_id=passage.id, published=True)
            session.add(chapter)
            chapter_rows[cid] = chapter
        await session.flush()

        translation = None if arabic_only else HadithTranslationEdition(
            source_edition_id=en_edition.id, translation_key=f"{COLLECTION_KEY}-en", language="en",
            translator_name=cfg["translator"], publisher_name=f"{cfg['package'].split()[0]} PyPI package",
            attribution_text=cfg["attribution"], published=True)
        if translation is not None:
            session.add(translation)
            await session.flush()

        count = 0
        narrations = []
        for h in data["hadiths"]:
            ar = by_key.get(f"{COLLECTION_KEY}{'' if arabic_only else '-ar'}:{h['id']}")
            if ar is None or h["chapterId"] not in book_rows:
                continue
            book, _, _ = book_rows[h["chapterId"]]
            narration = HadithNarration(
                collection_id=collection.id, book_id=book.id, chapter_id=chapter_rows[h["chapterId"]].id,
                collection_hadith_number=h["id"], canonical_reference=f"{COLLECTION_KEY}:{h['id']}",
                arabic_matn=ar.content, matn_sha256=ar.content_sha256, source_passage_id=ar.id, published=True)
            session.add(narration)
            narrations.append((narration, h["id"]))
            count += 1
        await session.flush()
        translated = 0
        for narration, hid in narrations:
            en = None if arabic_only else en_by_key.get(f"{COLLECTION_KEY}:{hid}")
            if en is not None:
                session.add(HadithTranslation(
                    translation_edition_id=translation.id, narration_id=narration.id, translated_text=en.content,
                    text_sha256=en.content_sha256, source_passage_id=en.id, published=True))
                translated += 1
        await session.commit()
        print(f"Published {cfg['title']}: {len(books)} books and {count} narrations ({translated} with English translation).")
    await db.dispose()


async def main() -> None:
    for cfg in base.all_collections().values():
        await publish(cfg)


if __name__ == "__main__":
    asyncio.run(main())
