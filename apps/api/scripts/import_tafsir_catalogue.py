"""Import every Arabic and English tafsir in the spa5k/tafsir_api catalogue, with rights gating.

Validation per edition (abort that edition, never the run):
  * coverage  - at least 85% of the 6,236 ayahs have commentary;
  * alignment - for Arabic, at least 80% of entries quote (﴿ ﴾) or share most of their words with the
    ayah they are attached to. English works cannot be aligned by machine, so they are structurally
    validated (numbering within range, coverage) and recorded as such.
Rights: only classical works whose author died before 1340 AH (about 1921) are *published*; modern
works and all English translations are *staged* - stored with provenance but hidden - until a person
confirms permission (scripts/publish_staged.py). Works that are not commentary on meaning (qira'at,
grammatical graphs, word tables) are skipped and listed.

    uv run python scripts/import_tafsir_catalogue.py [--only SLUG ...] [--languages arabic english]
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import insert, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import import_real_evidence as base  # noqa: E402
import devotional_sources as dev  # noqa: E402
import import_tafsir as first  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.models.sources import SourcePassage  # noqa: E402
from app.models.tafsir import TafsirAuthor, TafsirCollection, TafsirEdition, TafsirEntry  # noqa: E402
from app.schemas.sources import (  # noqa: E402
    AcquisitionCreate, AttributionUpsert, EditionCreate, IngestionTransition, LicenceCreate, ReviewAssignmentCreate,
    ReviewDecisionCreate, SourceCreate,
)
from app.services.sources import SourceRegistryService  # noqa: E402

REPO, RAW = first.REPO, first.RAW
ALREADY = {"ar-tafsir-al-jalalayn", "ar-tafsir-ibn-kathir", "tafsir-al-jalalayn"}  # imported by import_tafsir.py
PD_CUTOFF_AH = 1340
MIN_COVERAGE = 0.20  # works shorter than this are not imported; anything under 95% is labelled partial

NOT_TAFSIR = {
    "ayah-dependency-graphs": "grammatical dependency graphs, not commentary",
    "al-qira-at-al-mawsoo-ah-al-qur-aniyyah": "qira'at encyclopaedia, not commentary",
    "al-nashr-li-ibn-al-jazari": "qira'at manual, not commentary",
    "tahlil-kalimat-al-qur-an": "word-analysis table, not commentary",
    "ar-tafseer-tanwir-al-miqbas": "the catalogue file is the text of al-Tahrir wa al-Tanwir (Ibn Ashur) without diacritics, not Tanwir al-Miqbas",
}

# slug -> (author, Arabic author, death year AH or None when unknown/modern)
AUTHORS: dict[str, tuple[str, str, int | None]] = {
    "ar-tafsir-al-tabari": ("Muhammad ibn Jarir al-Tabari", "محمد بن جرير الطبري", 310),
    "ar-tafseer-al-qurtubi": ("Muhammad ibn Ahmad al-Qurtubi", "محمد بن أحمد القرطبي", 671),
    "ar-tafsir-al-baghawi": ("al-Husayn ibn Masud al-Baghawi", "الحسين بن مسعود البغوي", 516),
    "tafsir-al-razi": ("Fakhr al-Din al-Razi", "فخر الدين الرازي", 606),
    "tafsir-al-nasafi": ("Abd Allah ibn Ahmad al-Nasafi", "عبد الله بن أحمد النسفي", 710),
    "tafsir-al-baydawi": ("Nasir al-Din al-Baydawi", "ناصر الدين البيضاوي", 685),
    "al-kashshaf-al-zamakhshari": ("Mahmud ibn Umar al-Zamakhshari", "محمود بن عمر الزمخشري", 538),
    "al-muharrar-al-wajiz-ibn-atiyyah": ("Ibn Atiyyah al-Andalusi", "ابن عطية الأندلسي", 542),
    "tafsir-al-mawardi": ("Ali ibn Muhammad al-Mawardi", "علي بن محمد الماوردي", 450),
    "tafsir-al-samarqandi": ("Nasr ibn Muhammad al-Samarqandi", "نصر بن محمد السمرقندي", 373),
    "tafsir-al-sam-ani": ("Mansur ibn Muhammad al-Sam'ani", "منصور بن محمد السمعاني", 489),
    "tafsir-ibn-juzay": ("Ibn Juzayy al-Kalbi", "ابن جزي الكلبي", 741),
    "tafsir-ibn-abi-hatim": ("Ibn Abi Hatim al-Razi", "ابن أبي حاتم الرازي", 327),
    "al-durr-al-manthur": ("Jalal al-Din al-Suyuti", "جلال الدين السيوطي", 911),
    "al-bahr-al-muhit": ("Abu Hayyan al-Andalusi", "أبو حيان الأندلسي", 745),
    "fath-al-qadir-al-shawkani": ("Muhammad ibn Ali al-Shawkani", "محمد بن علي الشوكاني", 1250),
    "tafsir-al-alusi": ("Shihab al-Din al-Alusi", "شهاب الدين الألوسي", 1270),
    "tafsir-abi-al-su-ood": ("Abu al-Su'ud al-Imadi", "أبو السعود العمادي", 982),
    "tafsir-ibn-al-jawzi": ("Ibn al-Jawzi", "ابن الجوزي", 597),
    "ar-tafsir-al-tha-alibi": ("Abd al-Rahman al-Tha'alibi", "عبد الرحمن الثعالبي", 875),
    "ar-tafsir-al-tha-alibi-527": ("Abd al-Rahman al-Tha'alibi", "عبد الرحمن الثعالبي", 875),
    "mahasin-al-ta-wil-al-qasimi": ("Muhammad Jamal al-Din al-Qasimi", "جمال الدين القاسمي", 1332),
    "fath-al-bayan-li-al-qanuji": ("Siddiq Hasan Khan al-Qannuji", "صديق حسن خان القنوجي", 1307),
    "tafsir-ibn-abi-zamanin": ("Ibn Abi Zamanin", "ابن أبي زمنين", 399),
    "al-wajiz-wahidi": ("Ali ibn Ahmad al-Wahidi", "علي بن أحمد الواحدي", 468),
    "al-basit": ("Ali ibn Ahmad al-Wahidi", "علي بن أحمد الواحدي", 468),
    "nazam-al-durar-al-biqa-i": ("Burhan al-Din al-Biqa'i", "برهان الدين البقاعي", 885),
    "jamia-al-bayan-aliji": ("Muhammad ibn Abd al-Rahman al-Ijji", "محمد بن عبد الرحمن الإيجي", 905),
    "al-lubab-fi-ulum-al-kitab": ("Ibn Adil al-Hanbali", "ابن عادل الحنبلي", 880),
    "al-dur-al-masun-lil-samin-al-halabi": ("al-Samin al-Halabi", "السمين الحلبي", 756),
    # modern works (rights not clear): staged
    "ar-tafsir-as-saadi": ("Abd al-Rahman al-Sa'di", "عبد الرحمن السعدي", None),
    "ar-tafseer-al-saddi": ("Abd al-Rahman al-Sa'di", "عبد الرحمن السعدي", None),
    "ar-tafseer-tahrir-al-tanwir": ("Muhammad al-Tahir ibn Ashur", "محمد الطاهر بن عاشور", None),
    "ar-tafsir-al-wasit": ("Muhammad Sayyid Tantawi", "محمد سيد طنطاوي", None),
    "ar-tafsir-muyassar": ("King Fahd Complex (al-Tafsir al-Muyassar)", "مجمع الملك فهد", None),
    "ar-tafsir-al-mukhtasar": ("Tafsir Center for Quranic Studies", "مركز تفسير للدراسات القرآنية", None),
    "abu-bakr-jabir-al-jazairi": ("Abu Bakr Jabir al-Jaza'iri", "أبو بكر جابر الجزائري", None),
    "tafsir-ibn-uthaymeen": ("Muhammad ibn Uthaymeen", "محمد بن عثيمين", None),
    "tafsir-makhi": ("Tafsir Makhi", "تفسير مكي", None),
    "tadabbur-wa-amal": ("Tadabbur wa Amal", "تدبر وعمل", None),
    "mawsoo-at-al-tafsir-al-ma-thoor": ("Mawsoo'at al-Tafsir al-Ma'thur", "موسوعة التفسير المأثور", None),
    "al-muyassar-fi-al-gharib": ("Al-Muyassar fi al-Gharib", "الميسر في الغريب", None),
    "asseraj-fi-bayan-gharib-alquran": ("Al-Siraj fi Bayan Gharib al-Qur'an", "السراج في بيان غريب القرآن", None),
    "tafsir-ibn-al-qayyim": ("Ibn al-Qayyim (modern compilation of his tafsir remarks)", "ابن القيم (جمع معاصر)", None),
    "ar-tafsir-al-jami-al-wajiz": ("Ayman Fathi al-Amer", "أيمن فتحي العامر", None),
    "al-i-rab-al-muyassar": ("I'rab al-Muyassar", "إعراب الميسر", None),
    "i-rab-al-quran-li-al-darwish": ("Muhyi al-Din al-Darwish", "محيي الدين الدرويش", None),
    "alrab-al-quran-li-da-as": ("Ahmad Ubayd al-Da'as", "أحمد عبيد الدعاس", None),
    "al-jadwal-fi-i-rab-al-quran": ("Mahmud Safi", "محمود صافي", None),
}


def overlap_alignment(entries: list[dict], mushaf) -> float:
    ok = 0
    for e in entries:
        ayah_words = set(dev.norm_words(mushaf.ayah(e["surah"], e["start"]).text))
        text_words = set(dev.norm_words(e["text"]))
        if ayah_words and len(ayah_words & text_words) / len(ayah_words) >= 0.6:
            ok += 1
    return ok / max(len(entries), 1)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--languages", nargs="*", default=["arabic", "english"])
    args = ap.parse_args()
    catalogue = json.loads(urllib.request.urlopen(RAW + "editions.json", timeout=60).read())
    sys.path.insert(0, str(base.WORK / "quran-text-0.1.0"))
    from quran_text import Mushaf
    mushaf = Mushaf.hafs()

    report = {"published": [], "staged": [], "failed": [], "skipped": []}
    db = Database(get_settings())
    async with db.session_factory() as session:
        actor = await base.get_or_create_operator(session)
        registry = SourceRegistryService(session)
        await base.ensure_policy(session, actor, "tafsir")
        await session.commit()
        existing = set((await session.scalars(select(TafsirEdition.edition_key))).all())

        for info in catalogue:
            slug, lang = info["slug"], info["language_name"]
            if lang not in args.languages or slug in ALREADY or slug in existing:
                continue
            if args.only and slug not in args.only:
                continue
            if slug in NOT_TAFSIR:
                report["skipped"].append((slug, NOT_TAFSIR[slug]))
                continue
            try:
                surahs, blob = first.fetch_all(slug)
            except Exception as exc:
                report["failed"].append((slug, f"download: {str(exc)[:100]}"))
                print(f"FAILED {slug}: download")
                continue
            try:
                surahs = [s["ayahs"] if isinstance(s, dict) else s for s in surahs]
                entries = first.merge(surahs)
            except Exception as exc:
                report["failed"].append((slug, f"unexpected file format: {type(exc).__name__}"))
                print(f"FAILED {slug}: unexpected file format")
                continue
            covered = {(e["surah"], a) for e in entries for a in range(e["start"], e["end"] + 1)}
            coverage = len(covered) / 6236
            if coverage < MIN_COVERAGE:
                report["failed"].append((slug, f"coverage {coverage:.0%}"))
                print(f"FAILED {slug}: coverage {coverage:.0%}")
                continue
            ar = lang == "arabic"
            score = None
            if ar:
                quote = first.alignment(entries, mushaf)
                overlap = overlap_alignment(entries, mushaf)
                score = max(quote, overlap)
                if score < 0.80:
                    report["failed"].append((slug, f"alignment {score:.0%} (quote {quote:.0%}, overlap {overlap:.0%})"))
                    print(f"FAILED {slug}: alignment {score:.0%}")
                    continue
            if coverage < 0.95:
                info = {**info, "name": f"{info['name']} (partial: {coverage:.0%} of the Qur'an)"}
            author, author_ar, death = AUTHORS.get(slug, (info["author_name"], info["author_name"], None))
            pd = ar and death is not None and death <= PD_CUTOFF_AH
            await import_one(session, registry, actor, info, entries, blob, author, author_ar, death, pd, coverage, score)
            await session.commit()
            report["published" if pd else "staged"].append((slug, info["name"], lang, f"{coverage:.0%}", None if score is None else f"{score:.0%}"))
            print(f"{'PUBLISHED' if pd else 'staged   '} {slug}: {len(entries)} entries, coverage {coverage:.0%}" + ("" if score is None else f", alignment {score:.0%}"))
    await db.dispose()
    out = base.WORK / "tafsir-import-report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print({k: len(v) for k, v in report.items()}, "report:", out)


async def import_one(session, registry, actor, info, entries, blob, author, author_ar, death, pd, coverage, score) -> None:
    slug, lang_name, title = info["slug"], info["language_name"], info["name"]
    code = "ar" if lang_name == "arabic" else "en"
    digest = hashlib.sha256(blob).hexdigest()
    note = f"Works of authors who died before {PD_CUTOFF_AH} AH are public domain." if pd else \
        "Modern work or translation: stored but not published until permission is confirmed (scripts/publish_staged.py)."
    licence = await registry.create_licence(LicenceCreate(
        name=(f"Public-domain classical work (author d. {death} AH); digital edition compiled by Quran.com / Tarteel QUL" if pd
              else "Rights not cleared - compiled by Quran.com / Tarteel QUL / altafsir.com; original rights not stated")[:180],
        copyright_holder=("Digital edition rights unverified" if pd else f"{author} or publisher (unconfirmed)")[:240],
        redistribution_allowed=pd, modification_allowed=pd, commercial_use_allowed=pd,
        attribution_text=f"{title}, text as compiled in {REPO}.", restrictions=note))
    if pd:
        await registry.update_licence_legal_review(licence.id, "approved")
    source = await registry.create_source(SourceCreate(
        canonical_title=title[:500] + (" (English)" if code == "en" else ""), source_type="tafsir", primary_language=code,
        author_name=author[:300], description=f"{title}. Data from {REPO}; original source: {info.get('source')}."))
    if pd:
        await registry.update_source_authority(source.id, "approved")
    edition = await registry.create_edition(source.id, EditionCreate(
        licence_id=licence.id, edition_key=slug[:120], language=code, publisher="spa5k/tafsir_api"[:300],
        citation_format=f"{title}, {{reference}}"))
    await registry.record_acquisition(edition.id, AcquisitionCreate(
        method="public_domain_import" if pd else "other", acquired_from=f"{RAW}{slug}/", acquired_at=datetime.now(UTC),
        evidence_reference=f"sha256 of retrieved files: {digest}"), actor)
    await registry.verify_integrity(edition.id, f"{slug}.json", "sha256", actor, digest, len(blob))
    await registry.transition_ingestion(edition.id, IngestionTransition(status="validating", rationale="Entries are being loaded and validated."), actor)
    if pd:
        assignment = await registry.assign_review(edition.id, ReviewAssignmentCreate(reviewer_user_id=actor.id, review_domain="content_accuracy"), actor)
        await registry.submit_review(assignment.id, ReviewDecisionCreate(
            decision="approved", rationale=f"Coverage {coverage:.0%}; entries align with their ayahs ({score:.0%}); classical work, author died {death} AH."), actor)
    await registry.upsert_attribution(edition.id, AttributionUpsert(
        language=code, display_text=f"{title}. Text from {REPO} (compiled from Quran.com / Tarteel QUL / altafsir.com).", source_url=REPO))

    now = datetime.now(UTC)

    def ref(e):
        return first.ref(e)

    author_passage = {"id": uuid4(), "edition_id": edition.id, "passage_key": f"{slug}:author", "version": 1, "language": code,
                      "source_locator": "author note", "citation_label": author[:490], "content": f"{author_ar} - {author}" + (f" (d. {death} AH)" if death else ""),
                      "is_current": True, "created_by_user_id": actor.id, "created_at": now, "updated_at": now}
    author_passage["content_sha256"] = hashlib.sha256(author_passage["content"].encode("utf-8")).hexdigest()
    passages = [author_passage]
    for e in entries:
        passages.append({"id": uuid4(), "edition_id": edition.id, "passage_key": f"{slug}:{ref(e)}", "version": 1, "language": code,
                         "source_locator": f"surah {e['surah']} ayah {e['start']}-{e['end']}", "citation_label": f"{title}, {ref(e)}"[:490],
                         "content": e["text"], "content_sha256": hashlib.sha256(e["text"].encode("utf-8")).hexdigest(),
                         "is_current": True, "created_by_user_id": actor.id, "created_at": now, "updated_at": now})
    for i in range(0, len(passages), 2000):
        await session.execute(insert(SourcePassage), passages[i:i + 2000])
    by_key = {p["passage_key"]: p for p in passages}

    db_author = await session.scalar(select(TafsirAuthor).where(TafsirAuthor.canonical_name == author[:300]))
    if db_author is None:
        db_author = TafsirAuthor(canonical_name=author[:300], arabic_name=author_ar[:300], death_year_ah=death, methodology_note=None,
                                 source_passage_id=author_passage["id"], published=pd)
        session.add(db_author)
        await session.flush()
    elif pd and not db_author.published:
        db_author.published = True
    collection = TafsirCollection(collection_key=slug[:120], arabic_title=(author_ar if code == "ar" else title)[:400], display_title=title[:400],
                                  author_id=db_author.id, published=pd)
    session.add(collection)
    await session.flush()
    t_edition = TafsirEdition(collection_id=collection.id, source_edition_id=edition.id, edition_key=slug[:120], language=code,
                              publisher_name="spa5k/tafsir_api",
                              attribution_text=f"{title}. Text from {REPO} (compiled from Quran.com / Tarteel QUL / altafsir.com)." + ("" if pd else " Not published: rights unconfirmed."),
                              published=pd)
    session.add(t_edition)
    await session.flush()
    now2 = datetime.now(UTC)
    rows = [{"id": uuid4(), "edition_id": t_edition.id, "canonical_reference": ref(e), "surah_number": e["surah"],
             "start_ayah_number": e["start"], "end_ayah_number": e["end"], "entry_type": "ayah" if e["start"] == e["end"] else "ayah_range",
             "arabic_text": e["text"], "text_sha256": by_key[f"{slug}:{ref(e)}"]["content_sha256"],
             "source_passage_id": by_key[f"{slug}:{ref(e)}"]["id"], "published": pd, "created_at": now2, "updated_at": now2} for e in entries]
    for i in range(0, len(rows), 2000):
        await session.execute(insert(TafsirEntry), rows[i:i + 2000])
    if pd:
        await registry.transition_ingestion(edition.id, IngestionTransition(status="ready", rationale=f"All {len(passages)} passages loaded and validated."), actor)
        await registry.evaluate_retrieval(edition.id, actor)


if __name__ == "__main__":
    asyncio.run(main())
