"""Load the quran.ws tajweed corpus (CC-BY-4.0) next to the published Qur'an text.

Downloads @quran.ws/tajwid-rules and @quran.ws/tajwid-annotations from the npm registry,
verifies their published sha512 integrity, and renders each ayah's text *with waqf marks*
(the text the annotation offsets are measured against). Every span is bounds-checked and
qalqalah spans must land on a qalqalah letter, otherwise the import aborts.

    uv run python scripts/import_tajweed.py
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import sys
import tarfile
import urllib.request
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import import_real_evidence as base  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.models.quran import QuranAyah, QuranSurah  # noqa: E402
from app.models.tajweed import QuranAyahTajweed, QuranTajweedRule  # noqa: E402

sys.path.insert(0, str(base.WORK / "quran-text-0.1.0"))
from quran_text import Mushaf  # noqa: E402


def npm_file(package: str, filename: str) -> dict:
    meta = json.load(urllib.request.urlopen(f"https://registry.npmjs.org/{package.replace('/', '%2f')}/0.1.0", timeout=60))
    blob = urllib.request.urlopen(meta["dist"]["tarball"], timeout=120).read()
    algo, _, digest = meta["dist"]["integrity"].partition("-")
    if base64.b64encode(hashlib.new(algo, blob).digest()).decode() != digest:
        raise SystemExit(f"{package}: integrity mismatch, refusing to import")
    with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
        return json.load(tar.extractfile(f"package/{filename}"))


async def main() -> None:
    rules = npm_file("@quran.ws/tajwid-rules", "rules.json")
    ann = npm_file("@quran.ws/tajwid-annotations", "uthmani-hafs.json")
    version = ann["corpusVersion"]
    topics = {t["id"]: t["label"]["ar"] for t in rules["topics"]}
    cat_topic = {c["id"]: c["topic"] for c in rules["categories"]}
    hukum_topic = {h["id"]: cat_topic[h["category"]] for h in rules["hukums"]}
    mushaf = Mushaf.hafs()

    db = Database(get_settings())
    async with db.session_factory() as session:
        if await session.scalar(select(QuranAyahTajweed.id).limit(1)):
            print("Tajweed already imported, skipping.")
            return
        ayahs = {(s, a): i for i, s, a in (await session.execute(
            select(QuranAyah.id, QuranSurah.surah_number, QuranAyah.ayah_number).join(QuranSurah, QuranSurah.id == QuranAyah.surah_id))).all()}
        if not ayahs:
            raise SystemExit("Publish the Qur'an first (scripts/import_quran_reader.py).")
        for r in rules["rules"]:
            if r["id"] in set(ann["ruleIds"]):
                topic = hukum_topic[r["hukum"]]
                session.add(QuranTajweedRule(rule_id=r["id"], topic_id=topic, topic_label_ar=topics[topic],
                                             hukum_id=r["hukum"], label_ar=r["label"]["ar"]))
        count = spans_total = 0
        for ref, spans in ann["spans"].items():
            s, a = map(int, ref.split(":"))
            text = mushaf.ayah(s, a).render(marks=True, ayah_marks=False)
            cps = list(text)
            out = []
            for start, end, idx in spans:
                rid = ann["ruleIds"][idx]
                if not 0 <= start < end <= len(cps):
                    raise SystemExit(f"{ref}: span {start}-{end} is outside the ayah text; aborting")
                if rid.startswith("qalqalah") and not any(c in "قطبجد" for c in cps[start:end]):
                    raise SystemExit(f"{ref}: qalqalah span not on a qalqalah letter; aborting")
                out.append([start, end, rid])
            session.add(QuranAyahTajweed(ayah_id=ayahs[(s, a)], marked_text=text,
                                         spans_json=json.dumps(out, separators=(",", ":")), corpus_version=version))
            count += 1
            spans_total += len(out)
        await session.commit()
        print(f"Loaded tajweed corpus {version}: {spans_total} spans across {count} ayahs.")
    await db.dispose()


if __name__ == "__main__":
    asyncio.run(main())
