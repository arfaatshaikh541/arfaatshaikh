"""Publish the Qur'an into the reader tables (surahs, text edition, ayahs).

Run after scripts/import_real_evidence.py, which loads the approved source
passages this step links to. Uses QuranImportService, i.e. the same draft ->
validate -> review -> publish flow as the admin API. Juz and page numbers are
derived from the source data's own word offsets (no invented values).

    uv run python scripts/import_quran_reader.py
"""
from __future__ import annotations

import asyncio
import bisect
import hashlib
import json
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import import_real_evidence as base  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.models.quran import QuranSurah, QuranTextEdition  # noqa: E402
from app.models.sources import SourceEdition, SourcePassage  # noqa: E402
from app.schemas.quran import QuranImportAyahCreate, QuranImportManifestCreate, QuranImportReviewCreate  # noqa: E402
from app.services.quran_imports import QuranImportService  # noqa: E402

EDITION_KEY = "hafs-uthmani-quran-text-v3"


async def main() -> None:
    data = json.load(base.QURAN_JSON.open(encoding="utf-8"))
    words, ayah_starts = data["words"], data["ayah_starts"]
    juz_starts, page_starts = data["juz_starts"], data["page_starts"]

    db = Database(get_settings())
    async with db.session_factory() as session:
        source_edition = await session.scalar(select(SourceEdition).where(SourceEdition.edition_key == EDITION_KEY))
        if source_edition is None:
            raise SystemExit("Run scripts/import_real_evidence.py first (Qur'an source edition not found).")
        if await session.scalar(select(QuranTextEdition.id).where(QuranTextEdition.source_edition_id == source_edition.id)):
            print("Qur'an reader already published, skipping.")
            return
        actor = await base.get_or_create_operator(session)

        passages = {
            p.passage_key: p for p in await session.scalars(
                select(SourcePassage).where(SourcePassage.edition_id == source_edition.id, SourcePassage.is_current.is_(True)))
        }

        for s in data["surahs"]:
            session.add(QuranSurah(
                surah_number=s["number"], arabic_name=s["name_ar"], transliterated_name=s["name_en"],
                english_name=s["name_en"], ayah_count=s["ayah_count"], revelation_classification=s["revelation"],
            ))
        edition = QuranTextEdition(
            source_edition_id=source_edition.id, edition_key="hafs-uthmani", script_style="uthmani",
            recitation_system="Hafs an Asim", canonical=True, published=False,
        )
        session.add(edition)
        await session.flush()

        rows = []
        for s in data["surahs"]:
            for offset in range(s["ayah_count"]):
                g = s["first_ayah"] + offset
                word_index = ayah_starts[g]
                passage = passages[f"{s['number']}:{offset + 1}"]
                rows.append((s["number"], offset + 1, passage,
                             bisect.bisect_right(juz_starts, word_index),
                             bisect.bisect_right(page_starts, word_index)))
        manifest = "\n".join(
            f"{sn}:{an}\t{hashlib.sha256(p.content.encode('utf-8')).hexdigest()}\t{p.id}" for sn, an, p, _, _ in rows)

        service = QuranImportService(session)
        batch = await service.create_batch(QuranImportManifestCreate(
            text_edition_id=edition.id, manifest_version="1", expected_surah_count=114,
            expected_ayah_count=len(rows), manifest_sha256=hashlib.sha256(manifest.encode("utf-8")).hexdigest()), actor.id)
        for sn, an, passage, juz, page in rows:
            await service.add_ayah(batch.id, QuranImportAyahCreate(
                surah_number=sn, ayah_number=an, arabic_text=passage.content, source_passage_id=passage.id,
                juz_number=juz, page_number=page), actor.id)
        batch = await service.validate_batch(batch.id, actor.id)
        print("validation:", batch.status, batch.validation_summary)
        if batch.status != "review_pending":
            raise SystemExit("Validation failed; nothing published.")
        await service.review_batch(batch.id, actor.id, QuranImportReviewCreate(
            decision="approved",
            rationale="Text and counts validated against the approved source edition; manifest checksum matched."))
        await service.publish_batch(batch.id, actor.id)
        await session.commit()
        print(f"Published {len(rows)} ayahs across 114 surahs.")
    await db.dispose()


if __name__ == "__main__":
    asyncio.run(main())
