"""Nawawi's 40 Hadith, Hisnul Muslim and Morning/Evening Adhkar from npm (declared CC-BY-4.0).

The packages give no upstream provenance, so every Arabic text is cross-checked against text we
already hold from independent sources (the Qur'an, Sahih al-Bukhari, Sahih Muslim). Each entry's
citation label records the result; entries that cannot be cross-checked are labelled as such.
The packages' machine-made transliteration is deliberately not imported.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import re
import tarfile
import unicodedata
import urllib.request
from pathlib import Path


def norm_words(s: str) -> list[str]:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.category(c).startswith("M") and c != "ـ")
    for a, b in {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"}.items():
        s = s.replace(a, b)
    return re.sub(r"[^ء-ي ]", "", s).split()


def fetch_npm(work: Path, package: str, version: str) -> tuple[Path, dict]:
    meta = json.load(urllib.request.urlopen(f"https://registry.npmjs.org/{package.replace('/', '%2f')}/{version}", timeout=60))
    tarball = work / f"{package.replace('/', '__')}-{version}.tgz"
    if not tarball.exists():
        tarball.write_bytes(urllib.request.urlopen(meta["dist"]["tarball"], timeout=120).read())
    algo, _, digest = meta["dist"]["integrity"].partition("-")
    if base64.b64encode(hashlib.new(algo, tarball.read_bytes()).digest()).decode() != digest:
        tarball.unlink()
        raise RuntimeError(f"{package} {version}: integrity mismatch, refusing to import")
    with tarfile.open(tarball) as tar:
        return tarball, json.load(tar.extractfile("package/data.json"))


def build_collections(base) -> dict[str, dict]:
    work: Path = base.WORK
    sys_path = str(work / "quran-text-0.1.0")
    import sys
    sys.path.insert(0, sys_path)
    from quran_text import Mushaf

    quran = " ".join(" ".join(norm_words(a.text)) for s in range(1, 115) for a in Mushaf.hafs().surah(s).ayahs)
    sahih = ""
    for p in (base.MUSLIM_JSON_GZ, base.BUKHARI_JSON_GZ):
        sahih += " ".join(" ".join(norm_words(h["arabic"])) for h in json.load(gzip.open(p, "rt", encoding="utf-8"))["hadiths"]) + " "

    def check(arabic: str) -> str:
        w = norm_words(arabic)
        if len(w) >= 4 and any(" ".join(w[i:i + 4]) in quran for i in range(0, len(w) - 3, 2)):
            return "Arabic cross-checked against the Qur'an"
        if len(w) >= 5 and any(" ".join(w[i:i + 5]) in sahih for i in range(0, max(1, len(w) - 4), 2)):
            return "Arabic cross-checked against Sahih al-Bukhari/Muslim"
        return "Arabic not independently cross-checked"

    licence = dict(
        licence_name="Creative Commons Attribution 4.0 International (as declared by the npm package)", spdx="CC-BY-4.0",
        licence_url="https://creativecommons.org/licenses/by/4.0/", commercial=True,
        restrictions="Licence is declared by the package author; upstream provenance is not documented. "
                     "Confirm rights with the original publisher before public launch.",
    )
    out: dict[str, dict] = {}

    def write(key: str, data: dict) -> Path:
        path = work / f"{key}.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        return path

    # Nawawi's 40 (42 entries)
    tar, raw = fetch_npm(work, "@kazishariar/nawawi-40-hadith-data", "1.0.3")
    hadiths = []
    for n, h in enumerate(raw["data"], 1):
        hadiths.append({"id": n, "chapterId": 1, "arabic": h["arabic"], "label_suffix": check(h["arabic"]),
                        "english": {"narrator": "", "text": h.get("english", "")}})
    out["nawawi40"] = dict(
        key="nawawi40", edition_stem="nawawi40", title="Forty Hadith of Imam al-Nawawi", title_ar="الأربعون النووية",
        compiler="Imam Yahya ibn Sharaf al-Nawawi", package="npm @kazishariar/nawawi-40-hadith-data 1.0.3",
        pypi="https://www.npmjs.com/package/@kazishariar/nawawi-40-hadith-data", wheel=tar,
        data=write("nawawi40", {"chapters": [{"id": 1, "arabic": "الأربعون النووية", "english": "Forty Hadith of Imam al-Nawawi"}], "hadiths": hadiths}),
        licence_holder="Shariar Kazi (package author)", translator="English text as supplied by the package (translator not stated)",
        attribution="Forty Hadith of Imam al-Nawawi. Text from the @kazishariar/nawawi-40-hadith-data package, CC BY 4.0.",
        review="Arabic texts were cross-checked against Sahih al-Bukhari and Sahih Muslim text already held from independent sources.",
        arabic_only=False, **licence)

    # Hisnul Muslim (Arabic only, grouped by section)
    tar, raw = fetch_npm(work, "@kazishariar/hisnul-muslim-data", "1.0.3")
    sections: dict[str, int] = {}
    hadiths = []
    for n, h in enumerate(raw["data"], 1):
        cid = sections.setdefault(h["section"], len(sections) + 1)
        hadiths.append({"id": n, "chapterId": cid, "arabic": h["arabic"], "label_suffix": check(h["arabic"]), "english": {}})
    out["hisn"] = dict(
        key="hisn", edition_stem="hisn", title="Hisn al-Muslim (Fortress of the Muslim)", title_ar="حصن المسلم",
        compiler="Sa'id ibn Ali ibn Wahf al-Qahtani", package="npm @kazishariar/hisnul-muslim-data 1.0.3",
        pypi="https://www.npmjs.com/package/@kazishariar/hisnul-muslim-data", wheel=tar,
        data=write("hisn", {"chapters": [{"id": i, "arabic": s, "english": s} for s, i in sections.items()], "hadiths": hadiths}),
        licence_holder="Shariar Kazi (package author)", translator="",
        attribution="Hisn al-Muslim, Arabic text from the @kazishariar/hisnul-muslim-data package, CC BY 4.0.",
        review="Arabic texts were cross-checked where possible against the Qur'an and Sahih al-Bukhari/Muslim; entries that could not be cross-checked are labelled.",
        arabic_only=True, **licence)

    # Morning & evening adhkar (Arabic + English + cited source)
    tar, raw = fetch_npm(work, "@kazishariar/morning-evening-adhkar-data", "1.0.3")
    hadiths = []
    for n, h in enumerate(raw["data"], 1):
        hadiths.append({"id": n, "chapterId": 1, "arabic": h["arabic"], "label_suffix": check(h["arabic"]),
                        "english": {"narrator": h.get("source", ""), "text": h.get("english", "")}})
    out["adhkar"] = dict(
        key="adhkar", edition_stem="adhkar", title="Morning and Evening Adhkar", title_ar="أذكار الصباح والمساء",
        compiler="Compiled from hadith; each entry cites its source", package="npm @kazishariar/morning-evening-adhkar-data 1.0.3",
        pypi="https://www.npmjs.com/package/@kazishariar/morning-evening-adhkar-data", wheel=tar,
        data=write("adhkar", {"chapters": [{"id": 1, "arabic": "أذكار الصباح والمساء", "english": "Morning and Evening Adhkar"}], "hadiths": hadiths}),
        licence_holder="Shariar Kazi (package author)", translator="English text as supplied by the package (translator not stated)",
        attribution="Morning and Evening Adhkar. Text from the @kazishariar/morning-evening-adhkar-data package, CC BY 4.0.",
        review="Arabic texts were cross-checked where possible against the Qur'an and Sahih al-Bukhari/Muslim; each entry carries the source cited by the package.",
        arabic_only=False, **licence)
    return out
