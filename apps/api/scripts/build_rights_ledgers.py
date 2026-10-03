"""Build the per-edition and per-grader rights ledgers from the upstream catalogues themselves.

    uv run python scripts/build_rights_ledgers.py            # fetch, write data/rights-ledger-*.json
    uv run python scripts/build_rights_ledgers.py --check    # fetch again and fail if the committed ledgers are stale

Nothing here is typed from memory: every row is a line of the upstream catalogue, and every rights field the catalogue does not state
is recorded as NOT_DOCUMENTED. A ledger row can only say what the upstream file says; it never grants permission.
"""
import argparse
import hashlib
import json
import re
import sys
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
UA = {"User-Agent": "WorldOfIslam-ledger/1.0 (+https://app.arfaatshaikh.example)"}
TAFSIR_EDITIONS = "https://raw.githubusercontent.com/spa5k/tafsir_api/main/tafsir/editions.json"
TAFSIR_LICENCE = "https://raw.githubusercontent.com/spa5k/tafsir_api/main/LICENSE"
GRADES_INFO = "https://raw.githubusercontent.com/fawazahmed0/hadith-api/1/info.json"
GRADES_REFS = "https://raw.githubusercontent.com/fawazahmed0/hadith-api/1/References.md"
GRADES_LICENCE = "https://raw.githubusercontent.com/fawazahmed0/hadith-api/1/LICENSE"
ND = "NOT_DOCUMENTED"


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def tafsir_ledger() -> dict:
    raw, lic = get(TAFSIR_EDITIONS), get(TAFSIR_LICENCE)
    rows = []
    for e in sorted(json.loads(raw), key=lambda e: e["slug"]):
        host = re.sub(r"^https?://([^/]+).*$", r"\1", e.get("source") or "")
        rows.append({
            "slug": e["slug"], "work": e["name"], "author_as_listed": e.get("author_name"), "language": e.get("language_name"), "catalogue_id": e.get("id"), "listed_source": e.get("source"),
            "source_host": host or None, "publisher": ND, "editor": ND, "translator": ND, "edition_year": ND, "licence": ND, "rights_evidence": ND,
            "original_work_public_domain": ND, "digital_edition_rights": ND, "redistribution_allowed": "NOT_ESTABLISHED", "decision": "KEEP_HIDDEN",
        })
    return {
        "version": 1, "kind": "tafsir_editions", "upstream": TAFSIR_EDITIONS, "upstream_sha256": sha(raw),
        "repository_licence": {"url": TAFSIR_LICENCE, "sha256": sha(lic), "text_first_line": lic.decode().splitlines()[0], "covers": "the repository's software ('the Software'); it says nothing about the tafsir texts"},
        "finding": "The catalogue lists author, name, language and the site each text was taken from (quran.com, qul.tarteel.ai or altafsir.com). It states no licence, publisher, editor, translator or year for any edition.",
        "counts": {"editions": len(rows), "by_source_host": dict(Counter(r["source_host"] for r in rows)), "by_language": dict(Counter(r["language"] for r in rows))},
        "editions": rows,
    }


COLLECTION_RX = {"abudawud": r"abu ?da(w|)[eu]d", "ibnmajah": r"ibn ?majah", "nasai": r"nasai", "tirmidhi": r"tirmi(dh|d)i", "malik": r"malik"}
GRADER_TOKEN = {"al-albani": "albani", "shuaib al arnaut": "arnaut", "zubair ali zai": "zubair", "abu ghuddah": "ghuddah", "muhammad muhyi al-din abdul hamid": "abdul hamid",
                "muhammad fouad abd al-baqi": "abd al-baqi", "ahmad muhammad shakir": "shakir", "bashar awad maarouf": "maarouf", "salim al-hilali": "hilali"}


def grader_ledger() -> dict:
    raw, refs, lic = get(GRADES_INFO), get(GRADES_REFS), get(GRADES_LICENCE)
    info = json.loads(raw)
    works = []
    for line in refs.decode().splitlines():
        m = re.match(r"(https?://\S+?)(?:/book/(\d+))?\s+(.+?)(?:<br>)?\s*$", line.strip())
        if m and "backup" not in m.group(3):
            works.append({"url": m.group(1) + (f"/book/{m.group(2)}" if m.group(2) else ""), "book_id": m.group(2), "label": m.group(3).strip()})
    counts: Counter = Counter()
    for collection, body in info.items():
        for h in body.get("hadiths", []):
            for g in h.get("grades", []):
                counts[(collection, g.get("name"))] += 1
    rows = []
    for (collection, grader), n in sorted(counts.items()):
        token = GRADER_TOKEN.get((grader or "").lower(), (grader or "").lower())
        match = [w for w in works if token in w["label"].lower() and re.search(COLLECTION_RX.get(collection, collection), w["label"].lower())]
        rows.append({"collection": collection, "grader": grader, "grades_recorded": n, "printed_work_reference": match[0] if len(match) == 1 else None,
                     "work_reference_note": None if len(match) == 1 else "No single reference line in the upstream References.md ties this grader to a work for this collection",
                     "edition": ND, "page": ND, "licence": ND, "rights_evidence": ND, "grading_rights": "NOT_ESTABLISHED", "decision": "KEEP_HIDDEN"})
    return {
        "version": 1, "kind": "hadith_grader_sources", "upstream": GRADES_INFO, "upstream_sha256": sha(raw), "references": GRADES_REFS, "references_sha256": sha(refs),
        "repository_licence": {"url": GRADES_LICENCE, "sha256": sha(lic), "text_first_line": lic.decode().splitlines()[0].strip() or lic.decode().splitlines()[1]},
        "finding": "Each grade names a grader but no printed work, edition or page. The upstream References.md says the grades come from scans of printed editions on al-maktaba.org (and one archive.org item); the repository's Unlicense covers its own files, not the graders' published gradings.",
        "totals": {"grades": sum(counts.values()), "graders": len({g for _, g in counts}), "rows": len(rows)}, "graders": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    outputs = {"rights-ledger-tafsir.json": tafsir_ledger(), "rights-ledger-hadith-gradings.json": grader_ledger()}
    stale = []
    for name, ledger in outputs.items():
        path = ROOT / "data" / name
        text = json.dumps(ledger, ensure_ascii=False, indent=1) + "\n"
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(name)
        else:
            path.write_text(text, encoding="utf-8")
            print(name, {k: v for k, v in ledger.items() if k in ("counts", "totals")})
    if stale:
        print("stale (upstream or generator changed):", ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
