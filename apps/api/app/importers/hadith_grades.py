"""Hadith gradings from fawazahmed0/hadith-api (info.json at git tag 1), one record per hadith with one entry per grader.

Grades are copied verbatim and never reconciled or inferred. The compiling repository's own reference for each grader (its
References.md line) is kept verbatim on each grade. Fields the source does not contain (the grading work's title, edition
and page) stay empty. Rights in the compiled grades are NOT established, so the resulting dataset must stay hidden.
"""
from __future__ import annotations

import json
import re

from app.importers.acquire import fetch, sha256
from app.importers.base import AdapterResult, FetchResult, SourceAdapter

TAG = "1"
BASE = f"https://raw.githubusercontent.com/fawazahmed0/hadith-api/{TAG}"
COLLECTION_TITLES = {"abudawud": "Sunan Abi Dawud", "ibnmajah": "Sunan Ibn Majah", "malik": "Muwatta Malik", "nasai": "Sunan an-Nasa'i", "tirmidhi": "Jami' at-Tirmidhi"}
# grader named in info.json -> (collection, the book id the repository's References.md gives for that grader)
GRADER_BOOKS = {
    ("abudawud", "Al-Albani"): "1755", ("abudawud", "Shuaib Al Arnaut"): "32832", ("abudawud", "Muhammad Muhyi Al-Din Abdul Hamid"): "33759",
    ("nasai", "Al-Albani"): "783", ("nasai", "Abu Ghuddah"): "33865",
    ("tirmidhi", "Al-Albani"): "782", ("tirmidhi", "Ahmad Muhammad Shakir"): "33754", ("tirmidhi", "Bashar Awad Maarouf"): "33861",
    ("malik", "Salim al-Hilali"): "noor-book.com-3_20211020",
    ("ibnmajah", "Al-Albani"): "810", ("ibnmajah", "Muhammad Fouad Abd al-Baqi"): "1198", ("ibnmajah", "Shuaib Al Arnaut"): "33036",
}
REF_LINE = re.compile(r"^(https?://\S+?)\s+(.+?)(?:<br>)?\s*$")


def parse_references(text: str) -> dict[str, str]:
    """References.md lines of the form '<url> <description>' keyed by the last path segment (the book id) or the host."""
    refs: dict[str, str] = {}
    for line in text.splitlines():
        match = REF_LINE.match(line.strip())
        if match and "backup link" not in match.group(2):
            url, description = match.groups()
            refs[url.rstrip("/").rsplit("/", 1)[-1]] = f"{url} {description}".strip()
    return refs


def build_rows(info: dict, references: dict[str, str]) -> tuple[list[dict], dict]:
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
                book = GRADER_BOOKS.get((collection, g["name"]))
                reference = references.get(book) if book else (references.get("zubairalizai.com") if g["name"] == "Zubair Ali Zai" else None)
                grades.append({"grader": g["name"], "grade": g["grade"],
                               "grading_source": (f"al-maktaba.org/book/{book}" if book.isdigit() else f"archive.org/details/{book}") if book else ("zubairalizai.com (named in References.md; no page given)" if g["name"] == "Zubair Ali Zai" else "fawazahmed0/hadith-api info.json (the grader's own reference is not stated)"),
                               "source_reference_text": reference, "rights_status": "unverified", "verification_status": "unverified"})
            if not grades:
                continue
            number = hadith["hadithnumber"]
            book_no = hadith.get("reference", {}).get("book")
            section = sections.get(str(book_no)) if book_no is not None else None
            summary = "; ".join(f"{g['grader']}: {g['grade']}" for g in grades)
            rows.append({
                "id": f"hadithapi-{collection}-{number}", "entity_type": "hadith_grading", "title": f"Gradings of {title}, hadith {number}",
                "description": f"Grades recorded for {title}, hadith number {number}. {summary}. Each grader's judgement is listed separately and is not combined.",
                "source": "fawazahmed0/hadith-api info.json", "source_url": f"https://github.com/fawazahmed0/hadith-api/tree/{TAG}",
                "license": "Unlicense for the repository; rights in the compiled grades are not confirmed",
                "provenance": "Grades copied verbatim from info.json of fawazahmed0/hadith-api (tag 1); the repository's References.md names the source page of each grader's grades. Not independently re-checked against the graders' printed works.",
                "scholarly_status": "unreviewed", "confidence": 0,
                "source_work": f"{title}, with the graders' own works as compiled in fawazahmed0/hadith-api",
                "edition": f"hadith-api tag {TAG}", "chapter": f"Book {book_no}: {section}" if section else None, "language": "en",
                "publication_status": "dataset", "license_status": "LICENSE_REQUIRED", "provenance_status": "source_and_page_cited" if section else "source_cited",
                "tags": ["hadith-grading", collection],
                "attributes": {"collection": collection, "hadith_number": number, "arabic_number": hadith.get("arabicnumber"), "grades": grades,
                               "grade_labels_differ": len({g["grade"] for g in grades}) > 1},
            })
            stats["hadiths_with_grades"] += 1
            stats["grades"] += len(grades)
    return rows, stats


class HadithApiGrades(SourceAdapter):
    id = "hadith-api-grades"
    dataset_key = "hadith-grading"
    kind = "records"
    title = "Hadith gradings (fawazahmed0/hadith-api, per grader)"
    probe_urls = (f"{BASE}/info.json",)
    licence_summary = "Unlicense for the repository; rights in the compiled grades NOT established (dataset stays hidden)"
    max_rows = 30000

    def fetch(self, params: dict) -> FetchResult:
        raw = fetch(f"{BASE}/info.json", timeout=300)
        references = fetch(f"{BASE}/References.md").decode("utf-8", "replace")
        return FetchResult(version=f"tag {TAG}", checksum=sha256(raw), payload={"info": json.loads(raw), "references": references}, source_url=f"https://github.com/fawazahmed0/hadith-api/tree/{TAG}",
                           notes={"references_sha256": sha256(references.encode())})

    def build(self, fetched: FetchResult, params: dict) -> AdapterResult:
        rows, stats = build_rows(fetched.payload["info"], parse_references(fetched.payload["references"]))
        return AdapterResult(rows=rows, skipped={"placeholder_grades": stats["placeholder_grades_skipped"]}, stats=stats)
