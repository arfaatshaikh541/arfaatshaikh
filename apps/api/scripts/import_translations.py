"""Import Qur'an translations from the fawazahmed0/quran-api catalogue, with rights gating.

Every edition that passes validation is stored with its provenance. Only editions whose work is
clearly public domain are *published*; every other edition is *staged* (stored, hidden) until a
person confirms permission, because this catalogue has no per-edition licence field and republishes
many in-copyright works. Non-Muslim translators (the catalogue flags them) and translations from
groups outside mainstream Islam are excluded entirely and listed in the report.

Validation per edition: exactly 6,236 verses, (chapter, verse) numbering identical to the published
Arabic text, at least 99% non-empty verses, no edition flagged by its maintainer as OCR-damaged
is published.

    uv run python scripts/import_translations.py                 # everything
    uv run python scripts/import_translations.py --languages English Urdu
    uv run python scripts/import_translations.py --only eng-mohammedmarmadu
Publish staged editions later with scripts/publish_staged.py once permission is confirmed.
"""
from __future__ import annotations

import argparse
import asyncio
import concurrent.futures as cf
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
from app.core.config import get_settings  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.models.quran import QuranAyah, QuranAyahTranslation, QuranSurah, QuranTranslationEdition  # noqa: E402
from app.models.sources import Source, SourcePassage  # noqa: E402
from app.schemas.sources import (  # noqa: E402
    AcquisitionCreate, AttributionUpsert, EditionCreate, IngestionTransition, LicenceCreate,
    ReviewAssignmentCreate, ReviewDecisionCreate, SourceCreate,
)
from app.services.sources import SourceRegistryService  # noqa: E402

RAW = "https://raw.githubusercontent.com/fawazahmed0/quran-api/1/"
REPO = "https://github.com/fawazahmed0/quran-api"

# Works that are public domain (translator long deceased). Only these are published automatically.
PUBLIC_DOMAIN = {
    "eng-mohammedmarmadu": ("Marmaduke Pickthall, The Meaning of the Glorious Koran (1930)", 1936),
    "eng-yusufaliorig": ("Abdullah Yusuf Ali, The Holy Qur'an (1934 original edition)", 1953),
}

EXCLUDE_AUTHOR = re.compile(
    r"\b(ghulam|ahmadi|qadiani|rashad|khalifa|monotheist|submitter|bahai|baha'i|george sale|palmer|rodwell|dawood|"
    r"kasimirski|hamza boubakeur|montet|blachere|paret|henning|rudi paret)\b", re.I)


def fetch(url: str, retries: int = 4) -> bytes:
    for attempt in range(retries):
        try:
            return urllib.request.urlopen(url, timeout=90).read()
        except Exception:
            if attempt == retries - 1:
                raise
    raise RuntimeError("unreachable")


def clean(text: str) -> str:
    return " ".join(text.split())


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--languages", nargs="*", help="catalogue language names, e.g. English Urdu")
    ap.add_argument("--only", nargs="*", help="edition names, e.g. eng-mohammedmarmadu")
    args = ap.parse_args()

    catalogue = json.loads(fetch(RAW + "editions.json"))
    db = Database(get_settings())
    report: dict[str, list] = {"excluded": [], "failed": [], "published": [], "staged": []}
    async with db.session_factory() as session:
        actor = await base.get_or_create_operator(session)
        registry = SourceRegistryService(session)
        await base.ensure_policy(session, actor, "quran")
        await session.commit()

        ayah_ids = {(s, a): i for i, s, a in (await session.execute(
            select(QuranAyah.id, QuranSurah.surah_number, QuranAyah.ayah_number).join(QuranSurah, QuranSurah.id == QuranAyah.surah_id))).all()}
        if len(ayah_ids) != 6236:
            raise SystemExit("Publish the Qur'an first (scripts/import_quran_reader.py).")
        existing = set((await session.scalars(select(QuranTranslationEdition.translation_key))).all())

        todo = []
        for info in catalogue.values():
            name = info["name"]
            if args.only and name not in args.only:
                continue
            if args.languages and info["language"] not in args.languages:
                continue
            if name in existing:
                continue
            note = info.get("comments", "")
            if "non-muslim" in note.lower() or EXCLUDE_AUTHOR.search(info["author"]):
                report["excluded"].append((name, info["author"], "non-Muslim translator or outside mainstream Islam"))
                continue
            todo.append(info)
        print(f"{len(todo)} editions to import ({len(report['excluded'])} excluded)")

        def download(info: dict):
            return info, fetch(f"{RAW}editions/{info['name']}.min.json")

        for start in range(0, len(todo), 12):
            with cf.ThreadPoolExecutor(6) as ex:
                batch = list(ex.map(lambda i: _safe(download, i), todo[start:start + 12]))
            for result in batch:
                if isinstance(result, tuple) and result[0] == "error":
                    report["failed"].append((result[1]["name"], f"download: {result[2]}"))
                    continue
                info, blob = result
                name = info["name"]
                try:
                    verses = json.loads(blob)["quran"]
                except Exception as exc:
                    report["failed"].append((name, f"unreadable: {exc}"))
                    continue
                keys = [(v["chapter"], v["verse"]) for v in verses]
                texts = {(v["chapter"], v["verse"]): clean(v.get("text") or "") for v in verses}
                nonempty = sum(1 for t in texts.values() if t)
                if len(verses) != 6236 or set(keys) != set(ayah_ids) or nonempty < 0.99 * 6236:
                    report["failed"].append((name, f"validation: {len(verses)} verses, {nonempty} non-empty, numbering match={set(keys) == set(ayah_ids)}"))
                    continue
                ocr = "ocr" in info.get("comments", "").lower()
                published = name in PUBLIC_DOMAIN and not ocr
                await import_one(session, registry, actor, info, texts, blob, ayah_ids, published)
                await session.commit()
                report["published" if published else "staged"].append((name, info["author"], info["language"]))
            print(f"  ...{min(start + 12, len(todo))}/{len(todo)} done")
    await db.dispose()

    out = base.WORK / "translation-import-report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print(f"published {len(report['published'])}, staged {len(report['staged'])}, excluded {len(report['excluded'])}, failed {len(report['failed'])}")
    print(f"report: {out}")


def _safe(fn, arg):
    try:
        return fn(arg)
    except Exception as exc:  # network errors are reported, not fatal
        return ("error", arg, str(exc)[:120])


async def import_one(session, registry, actor, info, texts, blob, ayah_ids, published: bool) -> None:
    name = info["name"]
    author, language = info["author"], info["language"]
    title = f"Qur'an translation: {author} ({language})"
    lang_code = name.split("-")[0]
    digest = hashlib.sha256(blob).hexdigest()
    pd = PUBLIC_DOMAIN.get(name)
    licence = await registry.create_licence(LicenceCreate(
        name=(f"Public domain - {pd[0]}" if pd else "Rights not cleared - published by the quran-api catalogue without a per-edition licence")[:180],
        copyright_holder=(f"None (translator died {pd[1]})" if pd else f"{author} or publisher (unconfirmed)")[:240],
        redistribution_allowed=bool(pd), modification_allowed=False, commercial_use_allowed=bool(pd),
        attribution_text=f"{author}, Qur'an translation ({language}). Text via {REPO}.",
        restrictions=None if pd else "Stored but not published. Confirm the translator's or publisher's permission, then run scripts/publish_staged.py."))
    if pd:
        await registry.update_licence_legal_review(licence.id, "approved")
    source = await registry.create_source(SourceCreate(
        canonical_title=title[:500], source_type="quran", primary_language=lang_code if re.fullmatch(r"[a-z]{2,3}", lang_code) else "en",
        author_name=author[:300], description=f"{title}. Catalogue entry {name}; original source: {info.get('source') or 'not stated'}."))
    if pd:
        await registry.update_source_authority(source.id, "approved")
    edition = await registry.create_edition(source.id, EditionCreate(
        licence_id=licence.id, edition_key=name, language=lang_code if re.fullmatch(r"[a-z]{2,3}", lang_code) else "en",
        translator_name=author[:300], publisher=f"quran-api catalogue ({REPO})"[:300], citation_format=f"{title}, {{surah}}:{{ayah}}"))
    await registry.record_acquisition(edition.id, AcquisitionCreate(
        method="public_domain_import" if pd else "other", acquired_from=f"{RAW}editions/{name}.min.json",
        acquired_at=datetime.now(UTC), evidence_reference=f"sha256:{digest}"), actor)
    integrity_file = base.WORK / f"translation-{name}.json"
    integrity_file.write_bytes(blob)
    await registry.verify_integrity(edition.id, integrity_file.name, "sha256", actor, digest, len(blob))
    await registry.transition_ingestion(edition.id, IngestionTransition(status="validating", rationale="Verses are being loaded and validated."), actor)
    if pd:
        assignment = await registry.assign_review(edition.id, ReviewAssignmentCreate(reviewer_user_id=actor.id, review_domain="content_accuracy"), actor)
        await registry.submit_review(assignment.id, ReviewDecisionCreate(
            decision="approved", rationale="6,236 verses, numbering identical to the published Arabic, at least 99% non-empty; public-domain work."), actor)
    await registry.upsert_attribution(edition.id, AttributionUpsert(
        language="en", display_text=f"{author}, Qur'an translation ({language}). Text via {REPO}.", source_url=REPO))

    now = datetime.now(UTC)
    passages = []
    for (s, a), text in sorted(texts.items()):
        passages.append({
            "id": uuid4(), "edition_id": edition.id, "passage_key": f"{name}:{s}:{a}", "version": 1, "language": edition.language,
            "source_locator": f"{name} {s}:{a}", "citation_label": f"{author}, Qur'an {s}:{a}", "content": text,
            "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "is_current": True,
            "created_by_user_id": actor.id, "created_at": now, "updated_at": now})
    await session.execute(insert(SourcePassage), passages)
    t_edition = QuranTranslationEdition(
        source_edition_id=edition.id, translation_key=name, language=edition.language, translator_name=author[:300],
        display_name=f"{author} ({language})"[:300], published=published)
    session.add(t_edition)
    await session.flush()
    by_key = {p["passage_key"]: p for p in passages}
    await session.execute(insert(QuranAyahTranslation), [{
        "id": uuid4(), "translation_edition_id": t_edition.id, "ayah_id": ayah_ids[(s, a)], "translated_text": p["content"],
        "text_sha256": p["content_sha256"], "source_passage_id": p["id"], "published": published, "created_at": now, "updated_at": now}
        for (s, a) in sorted(texts) for p in [by_key[f"{name}:{s}:{a}"]]])
    if pd:
        await registry.transition_ingestion(edition.id, IngestionTransition(status="ready", rationale="All 6,236 verses loaded and validated."), actor)
        eligibility = await registry.evaluate_retrieval(edition.id, actor)
        if eligibility.eligible and language == "English":
            rows = list((await session.scalars(select(SourcePassage).where(SourcePassage.edition_id == edition.id))).all())
            await base.bulk_project(session, actor, source, edition, rows)


if __name__ == "__main__":
    asyncio.run(main())
