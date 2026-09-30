"""Publish classical Arabic tafsir (Jalalayn, Ibn Kathir) plus the English Jalalayn into the Tafsir reader.

Data comes from the open spa5k/tafsir_api repository (itself compiled from Quran.com / Tarteel QUL
and altafsir.com). The repository's MIT licence covers code only, so the record states plainly that
rights in the digital editions are unverified. The Arabic works are medieval (the authors died
between 774 and 911 AH), so the texts themselves are in the public domain. The English Jalalayn is a
modern translation and is recorded as non-commercial only.

Alignment check: each Arabic entry must quote words from the ayah it is attached to, or the
import aborts (threshold 90%). Consecutive ayahs with identical text are merged into one range.

    uv run python scripts/import_tafsir.py
"""
from __future__ import annotations

import asyncio
import concurrent.futures as cf
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import import_real_evidence as base  # noqa: E402
import devotional_sources as dev  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.models.sources import Source, SourceEdition, SourcePassage  # noqa: E402
from app.models.tafsir import (  # noqa: E402
    TafsirAuthor, TafsirCollection, TafsirEdition, TafsirEntry, TafsirTranslation, TafsirTranslationEdition,
)
from app.schemas.sources import (  # noqa: E402
    AcquisitionCreate, AttributionUpsert, EditionCreate, IngestionTransition, LicenceCreate, SourceCreate,
)
from app.services.sources import SourceRegistryService  # noqa: E402

RAW = "https://raw.githubusercontent.com/spa5k/tafsir_api/main/tafsir/"
REPO = "https://github.com/spa5k/tafsir_api"

ARABIC = [
    dict(key="jalalayn", slug="ar-tafsir-al-jalalayn", title="Tafsir al-Jalalayn", title_ar="تفسير الجلالين",
         author="Jalal al-Din al-Mahalli and Jalal al-Din al-Suyuti", author_ar="جلال الدين المحلي وجلال الدين السيوطي", death=911,
         note="Begun by al-Mahalli (d. 864 AH) and completed by al-Suyuti (d. 911 AH)."),
    dict(key="ibn-kathir", slug="ar-tafsir-ibn-kathir", title="Tafsir Ibn Kathir (Arabic)", title_ar="تفسير القرآن العظيم لابن كثير",
         author="Ismail ibn Kathir", author_ar="إسماعيل بن كثير", death=774, note="Ismail ibn Kathir died in 774 AH."),
]
ENGLISH = dict(key="jalalayn-en", slug="tafsir-al-jalalayn", of="jalalayn", title="Tafsir al-Jalalayn (English)")


def fetch_all(slug: str) -> tuple[list[list[dict]], bytes]:
    def one(n: int) -> bytes:
        for attempt in range(4):
            try:
                return urllib.request.urlopen(f"{RAW}{slug}/{n}.json", timeout=60).read()
            except urllib.error.HTTPError as exc:
                if exc.code == 404:  # the source has no file for this surah: treated as no commentary
                    return b"[]"
                if attempt == 3:
                    raise
            except Exception:
                if attempt == 3:
                    raise
        raise RuntimeError("unreachable")
    with cf.ThreadPoolExecutor(8) as ex:
        blobs = list(ex.map(one, range(1, 115)))
    return [json.loads(b) for b in blobs], b"".join(blobs)


def merge(surahs: list[list[dict]]) -> list[dict]:
    """Merge consecutive ayahs with identical text into ranges."""
    out: list[dict] = []
    for items in surahs:
        for it in sorted(items, key=lambda x: x["ayah"]):
            text = it["text"].strip()
            last = out[-1] if out else None
            if last and last["surah"] == it["surah"] and last["text"] == text and last["end"] + 1 == it["ayah"]:
                last["end"] = it["ayah"]
            else:
                out.append({"surah": it["surah"], "start": it["ayah"], "end": it["ayah"], "text": text})
    return out


def alignment(entries: list[dict], mushaf) -> float:
    ok = total = 0
    for e in entries:
        quoted = [dev.norm_words(q) for q in re.findall(r"﴿([^﴾]+)﴾", e["text"])]
        quoted = [q for q in quoted if q]
        if not quoted:
            continue
        total += 1
        own = set()
        for a in range(e["start"], e["end"] + 1):
            own.update(dev.norm_words(mushaf.ayah(e["surah"], a).text))
        if any(q[0] in own for q in quoted):
            ok += 1
    return ok / max(total, 1)


def ref(e: dict) -> str:
    return f"{e['surah']}:{e['start']}" if e["start"] == e["end"] else f"{e['surah']}:{e['start']}-{e['end']}"


async def govern(session, actor, *, title, title_ar, source_lang, edition_key, lang, author_name, licence, blob_path, review, attribution, translator=None):
    return await base.govern_edition(
        session, actor,
        licence_payload=licence,
        source_payload=SourceCreate(canonical_title=title, original_title=title_ar, source_type="tafsir", primary_language=source_lang,
                                    author_name=author_name, description=f"{title}. Data from {REPO}."),
        edition_payload=EditionCreate(edition_key=edition_key, language=lang, translator_name=translator,
                                      publisher="spa5k/tafsir_api (compiled from Quran.com / Tarteel QUL / altafsir.com)",
                                      citation_format=f"{title}, {{reference}}"),
        acquisition=AcquisitionCreate(method="public_domain_import" if lang == "ar" else "other", acquired_from=REPO,
                                      acquired_at=datetime.now(UTC), evidence_reference="sha256 of the retrieved files is recorded as the integrity digest"),
        integrity_path=blob_path, review_rationale=review,
    )


async def main() -> None:
    sys.path.insert(0, str(base.WORK / "quran-text-0.1.0"))
    from quran_text import Mushaf
    mushaf = Mushaf.hafs()
    db = Database(get_settings())
    async with db.session_factory() as session:
        actor = await base.get_or_create_operator(session)
        registry = SourceRegistryService(session)
        await base.ensure_policy(session, actor, "tafsir")
        await session.commit()
        entries_by_collection: dict[str, list[tuple[TafsirEntry, dict]]] = {}

        for cfg in ARABIC:
            if await session.scalar(select(TafsirCollection.id).where(TafsirCollection.collection_key == cfg["key"])):
                print(f"{cfg['title']} already imported, skipping.")
                continue
            print(f"Fetching {cfg['title']}...")
            surahs, blob = fetch_all(cfg["slug"])
            entries = merge(surahs)
            score = alignment(entries, mushaf)
            print(f"  {len(entries)} entries, ayah-quotation alignment {score:.1%}")
            if score < 0.90:
                raise SystemExit(f"{cfg['title']}: alignment below 90%, refusing to import")
            blob_path = base.WORK / f"tafsir-{cfg['key']}.json"
            blob_path.write_bytes(blob)
            licence = LicenceCreate(
                name="Public-domain classical work; digital edition compiled by Quran.com / Tarteel QUL (terms not stated)",
                copyright_holder="Original author deceased centuries ago; digital edition rights unverified",
                redistribution_allowed=True, modification_allowed=True, commercial_use_allowed=True,
                attribution_text=f"{cfg['title']}, text as compiled in {REPO} from Quran.com / Tarteel QUL.",
                restrictions="The work is public domain; rights in the digital edition are not documented. Confirm before public launch.")
            source, edition = await govern(
                session, actor, title=cfg["title"], title_ar=cfg["title_ar"], source_lang="ar", edition_key=f"{cfg['key']}-ar", lang="ar",
                author_name=cfg["author"], licence=licence, blob_path=blob_path,
                review=f"Each entry quotes words from the ayah it is attached to (alignment {score:.1%}); ayah coverage and text spot-checked against the known work.",
                attribution=None)
            await registry.upsert_attribution(edition.id, AttributionUpsert(
                language="ar", display_text=f"{cfg['title_ar']}. النص من {REPO}.", source_url=REPO))
            rows = [(f"{cfg['key']}:author", "author note", f"{cfg['author']}", f"{cfg['author_ar']} - {cfg['note']}")]
            rows += [(f"{cfg['key']}:{ref(e)}", f"surah {e['surah']} ayah {e['start']}-{e['end']}", f"{cfg['title']}, {ref(e)}", e["text"]) for e in entries]
            passages = base.bulk_add_passages(session, edition, actor, rows)
            await session.flush()
            by_key = {p.passage_key: p for p in passages}
            await registry.transition_ingestion(edition.id, IngestionTransition(status="ready", rationale=f"All {len(passages)} passages loaded and aligned."), actor)
            await base.bulk_project(session, actor, source, edition, passages)

            author = TafsirAuthor(canonical_name=cfg["author"], arabic_name=cfg["author_ar"], death_year_ah=cfg["death"],
                                  methodology_note=cfg["note"], source_passage_id=by_key[f"{cfg['key']}:author"].id, published=True)
            session.add(author)
            await session.flush()
            collection = TafsirCollection(collection_key=cfg["key"], arabic_title=cfg["title_ar"], display_title=cfg["title"],
                                          author_id=author.id, published=True)
            session.add(collection)
            await session.flush()
            t_edition = TafsirEdition(collection_id=collection.id, source_edition_id=edition.id, edition_key=f"{cfg['key']}-ar",
                                      language="ar", publisher_name="spa5k/tafsir_api",
                                      attribution_text=f"{cfg['title']}. Text from {REPO} (compiled from Quran.com / Tarteel QUL).", published=True)
            session.add(t_edition)
            await session.flush()
            built = []
            for e in entries:
                p = by_key[f"{cfg['key']}:{ref(e)}"]
                row = TafsirEntry(edition_id=t_edition.id, canonical_reference=ref(e), surah_number=e["surah"], start_ayah_number=e["start"],
                                  end_ayah_number=e["end"], entry_type="ayah" if e["start"] == e["end"] else "ayah_range",
                                  arabic_text=e["text"], text_sha256=p.content_sha256, source_passage_id=p.id, published=True)
                session.add(row)
                built.append((row, e))
            await session.flush()
            entries_by_collection[cfg["key"]] = built
            await session.commit()
            print(f"  published {len(built)} entries")

        # English Jalalayn, aligned ayah by ayah to the Arabic entries.
        if await session.scalar(select(TafsirTranslationEdition.id).where(TafsirTranslationEdition.translation_key == ENGLISH["key"])):
            print("English Jalalayn already imported, skipping.")
        else:
            t_edition = await session.scalar(select(TafsirEdition).where(TafsirEdition.edition_key == "jalalayn-ar"))
            if t_edition is None:
                raise SystemExit("Arabic Jalalayn must be imported first.")
            print("Fetching Tafsir al-Jalalayn (English)...")
            surahs, blob = fetch_all(ENGLISH["slug"])
            en = {(it["surah"], it["ayah"]): it["text"].strip() for items in surahs for it in items}
            arabic_entries = list((await session.scalars(select(TafsirEntry).where(TafsirEntry.edition_id == t_edition.id))).all())
            pairs = [(row, en[(row.surah_number, row.start_ayah_number)]) for row in arabic_entries
                     if row.start_ayah_number == row.end_ayah_number and (row.surah_number, row.start_ayah_number) in en]
            print(f"  {len(pairs)} of {len(arabic_entries)} entries have an aligned English text")
            if len(pairs) < 0.9 * len(arabic_entries):
                raise SystemExit("English alignment too low, refusing to import")
            blob_path = base.WORK / "tafsir-jalalayn-en.json"
            blob_path.write_bytes(blob)
            licence = LicenceCreate(
                name="Modern English translation of Tafsir al-Jalalayn as distributed by Quran.com / Tarteel QUL / altafsir.com",
                copyright_holder="Translator / publisher as credited by altafsir.com (to be confirmed)",
                redistribution_allowed=True, modification_allowed=False, commercial_use_allowed=False,
                attribution_text="Tafsir al-Jalalayn, English translation as distributed via Quran.com / Tarteel QUL (credit to be confirmed).",
                restrictions="Modern translation: non-commercial use only until the rights holder's terms are confirmed.")
            source, edition = await govern(
                session, actor, title="Tafsir al-Jalalayn (English translation)", title_ar="تفسير الجلالين (ترجمة إنجليزية)", source_lang="en",
                edition_key="jalalayn-en", lang="en", author_name="Jalal al-Din al-Mahalli and Jalal al-Din al-Suyuti", licence=licence,
                blob_path=blob_path, review="English texts align ayah-by-ayah with the reviewed Arabic entries.", attribution=None,
                translator="Translator credit to be confirmed")
            await registry.upsert_attribution(edition.id, AttributionUpsert(
                language="en", display_text="Tafsir al-Jalalayn, English translation as distributed via Quran.com / Tarteel QUL.", source_url=REPO))
            rows = [(f"jalalayn-en:{r.canonical_reference}", f"surah {r.surah_number} ayah {r.start_ayah_number}",
                     f"Tafsir al-Jalalayn (English), {r.canonical_reference}", txt) for r, txt in pairs]
            passages = base.bulk_add_passages(session, edition, actor, rows)
            await session.flush()
            by_key = {p.passage_key: p for p in passages}
            await registry.transition_ingestion(edition.id, IngestionTransition(status="ready", rationale=f"All {len(passages)} English passages loaded."), actor)
            await base.bulk_project(session, actor, source, edition, passages)
            te = TafsirTranslationEdition(tafsir_edition_id=t_edition.id, source_edition_id=edition.id, translation_key=ENGLISH["key"],
                                          language="en", translator_name="Translator credit to be confirmed", publisher_name="Quran.com / Tarteel QUL",
                                          attribution_text="Tafsir al-Jalalayn, English translation as distributed via Quran.com / Tarteel QUL.", published=True)
            session.add(te)
            await session.flush()
            for r, txt in pairs:
                p = by_key[f"jalalayn-en:{r.canonical_reference}"]
                session.add(TafsirTranslation(translation_edition_id=te.id, tafsir_entry_id=r.id, translated_text=txt,
                                              text_sha256=p.content_sha256, source_passage_id=p.id, published=True))
            await session.commit()
            print(f"  published {len(pairs)} English entries")
    await db.dispose()


if __name__ == "__main__":
    asyncio.run(main())
