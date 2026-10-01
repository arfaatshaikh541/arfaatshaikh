"""Build hadith-grading knowledge records from fawazahmed0/hadith-api (info.json at git tag 1).

    uv run python scripts/build_hadith_grading_records.py --out /tmp/hadith-gradings.json
    uv run python scripts/import_knowledge_records.py --dataset hadith-grading --file /tmp/hadith-gradings.0.json ...

Each record is one hadith with EVERY grade the file lists, one entry per grader, side by side: different graders'
differing grades are kept, never merged or ranked, and a missing grade is never filled in. Grades are copied verbatim.
The grades come from the graders' own works as compiled by the repository author (References.md names the al-maktaba.org
book of each); the repository is dedicated to the public domain (Unlicense) but rights in the compiled grades are not
established, so the dataset stays staged until an owner confirms them.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _acquire import fetch, sha256  # noqa: E402

TAG = "1"
BASE = f"https://raw.githubusercontent.com/fawazahmed0/hadith-api/{TAG}"
COLLECTION_TITLES = {"abudawud": "Sunan Abi Dawud", "ibnmajah": "Sunan Ibn Majah", "malik": "Muwatta Malik", "nasai": "Sunan an-Nasa'i", "tirmidhi": "Jami' at-Tirmidhi"}
# From References.md of the same repository tag: the page each grader's grades were taken from.
GRADING_SOURCES = {
    ("abudawud", "Al-Albani"): "al-maktaba.org/book/1755", ("abudawud", "Shuaib Al Arnaut"): "al-maktaba.org/book/32832",
    ("abudawud", "Muhammad Muhyi Al-Din Abdul Hamid"): "al-maktaba.org/book/33759",
    ("nasai", "Al-Albani"): "al-maktaba.org/book/783", ("nasai", "Abu Ghuddah"): "al-maktaba.org/book/33865",
    ("tirmidhi", "Al-Albani"): "al-maktaba.org/book/782", ("tirmidhi", "Ahmad Muhammad Shakir"): "al-maktaba.org/book/33754",
    ("tirmidhi", "Bashar Awad Maarouf"): "al-maktaba.org/book/33861",
    ("ibnmajah", "Al-Albani"): "al-maktaba.org/book/810", ("ibnmajah", "Muhammad Fouad Abd al-Baqi"): "al-maktaba.org/book/1198",
    ("ibnmajah", "Shuaib Al Arnaut"): "al-maktaba.org/book/33036",
    ("malik", "Salim al-Hilali"): "archive.org/details/noor-book.com-3_20211020",
}
ZUBAIR = "zubairalizai.com (named in References.md; no page given)"


def build(info: dict) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    stats = {"hadiths_with_grades": 0, "grades": 0, "placeholder_grades_skipped": 0}
    for collection, title in COLLECTION_TITLES.items():
        data = info[collection]
        sections = data["metadata"]["sections"]
        for hadith in data["hadiths"]:
            grades = []
            for g in hadith["grades"]:
                if not g.get("grade") or g["grade"].strip() in {"-", ""}:
                    stats["placeholder_grades_skipped"] += 1  # the file has no grade here: nothing is recorded
                    continue
                source = GRADING_SOURCES.get((collection, g["name"])) or (ZUBAIR if g["name"] == "Zubair Ali Zai" else "fawazahmed0/hadith-api info.json (the grader's own reference is not stated)")
                grades.append({"grader": g["name"], "grade": g["grade"], "grading_source": source})
            if not grades:
                continue
            number = hadith["hadithnumber"]
            book = hadith.get("reference", {}).get("book")
            section = sections.get(str(book)) if book is not None else None
            summary = "; ".join(f"{g['grader']}: {g['grade']}" for g in grades)
            rows.append({
                "id": f"hadithapi-{collection}-{number}", "entity_type": "hadith_grading",
                "title": f"Gradings of {title}, hadith {number}",
                "description": f"Grades recorded for {title}, hadith number {number}. {summary}. Each grader's judgement is listed separately and is not combined.",
                "source": "fawazahmed0/hadith-api info.json", "source_url": f"https://github.com/fawazahmed0/hadith-api/tree/{TAG}",
                "license": "Unlicense for the repository; rights in the compiled grades are not confirmed",
                "provenance": "Grades copied verbatim from info.json of fawazahmed0/hadith-api (tag 1); the repository's References.md names the source page of each grader's grades. Not independently re-checked against the graders' printed works.",
                "scholarly_status": "unreviewed", "confidence": 0,
                "source_work": f"{title}, with the graders' own works as compiled in fawazahmed0/hadith-api",
                "edition": f"hadith-api tag {TAG}", "chapter": f"Book {book}: {section}" if section else None, "language": "en",
                "publication_status": "dataset", "license_status": "LICENSE_REQUIRED", "provenance_status": "source_and_page_cited" if section else "source_cited",
                "tags": ["hadith-grading", collection],
                "attributes": {"collection": collection, "hadith_number": number, "arabic_number": hadith.get("arabicnumber"), "grades": grades,
                               "grade_labels_differ": len({g["grade"] for g in grades}) > 1},
            })
            stats["hadiths_with_grades"] += 1
            stats["grades"] += len(grades)
    return rows, stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--chunk", type=int, default=5000)
    ap.add_argument("--info", help="a previously downloaded info.json")
    args = ap.parse_args()
    raw = Path(args.info).read_bytes() if args.info else fetch(f"{BASE}/info.json", timeout=300)
    rows, stats = build(json.loads(raw))
    out = Path(args.out)
    for index in range(0, len(rows), args.chunk):
        out.with_suffix(f".{index // args.chunk}.json").write_text(json.dumps(rows[index:index + args.chunk], ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"info_json_sha256": sha256(raw), "records": len(rows), **stats, "chunks": -(-len(rows) // args.chunk)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
