"""Regenerate docs/DATA_READINESS.md from data/source-manifest.json (the manifest is the single source of truth).

    uv run python scripts/generate_data_readiness.py          # write
    uv run python scripts/generate_data_readiness.py --check  # exit 1 if the file is out of date
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.manifest import load_manifest, manifest_path  # noqa: E402

ORDER = ["VERIFIED", "NEEDS_REVIEW", "LICENSE_REQUIRED", "PROVENANCE_UNCLEAR", "UNAVAILABLE", "OWNER_UPLOAD_REQUIRED"]
MEANING = {
    "VERIFIED": "Source, licence and content checks done; safe to publish as described.",
    "NEEDS_REVIEW": "Usable and published/staged as stated, but a person must confirm a caveat listed below.",
    "LICENSE_REQUIRED": "Content exists but may not be shown publicly until the rights holder's permission is recorded.",
    "PROVENANCE_UNCLEAR": "The upstream origin could not be established; hidden until it can be.",
    "UNAVAILABLE": "A legitimate source exists but could not be reached from the build environment; run the importer elsewhere.",
    "OWNER_UPLOAD_REQUIRED": "No dataset is loaded. The importer, schema and empty-state UI are ready; supply an authorised dataset.",
}


DOMAIN_STATUSES = {
    "READY": "Real, verified, publishable data is published for the whole scope of the domain.",
    "PARTIALLY_READY": "Real data is published, but only for part of the scope (stated in Remaining Action).",
    "NEEDS_LICENSE": "Real data is imported and staged; the right to publish it is not established.",
    "NEEDS_PROVENANCE": "Data exists but its origin cannot be established; not imported or not published.",
    "SOURCE_UNAVAILABLE": "A legitimate source exists but could not be reached or accessed from the build environment.",
    "OWNER_DATA_REQUIRED": "No openly verifiable source was found; the owner must supply an authorised dataset.",
    "NOT_IMPLEMENTED": "The code needed to hold or show the data does not exist.",
}
# dataset id -> (domain label, importer, admin workflow, frontend, status assigned after reading the manifest entry and docs/SOURCE_VERIFICATION.md)
KNOWLEDGE_IMPORTER = "`import_knowledge_records.py`: preview, all-or-nothing, rollback"
LISTING_IMPORTER = "`import_directory.py`: preview, all-or-nothing, rollback"
ADMIN = "Preview, import, verify, publish, unpublish, rollback, provenance and audit (Data & trust)"
AUDIO_ADMIN = "Admin API: create recitation, add recordings, publish (hosted needs a permitting licence and a recorded authorisation)"
DOMAINS = [
    ("fiqh-rulings", "Fiqh", KNOWLEDGE_IMPORTER, "/knowledge/fiqh, per-madhhab filter", "OWNER_DATA_REQUIRED"),
    ("aqeedah", "Aqeedah", KNOWLEDGE_IMPORTER, "/knowledge/aqeedah, per-school filter", "OWNER_DATA_REQUIRED"),
    ("seerah", "Seerah", KNOWLEDGE_IMPORTER, "/knowledge/seerah, reliability category", "OWNER_DATA_REQUIRED"),
    ("hadith-grading", "Hadith grading", KNOWLEDGE_IMPORTER + "; `build_hadith_grading_records.py`", "/knowledge/hadith_grading, one row per grader", "NEEDS_LICENSE"),
    ("terminology", "Islamic terminology", KNOWLEDGE_IMPORTER, "/knowledge/terminology", "OWNER_DATA_REQUIRED"),
    ("library-works", "Islamic library", KNOWLEDGE_IMPORTER + "; metadata or external link only", "/knowledge/library_work", "SOURCE_UNAVAILABLE"),
    ("history", "Islamic history", KNOWLEDGE_IMPORTER, "/knowledge/history", "OWNER_DATA_REQUIRED"),
    ("civilization", "Islamic civilization", KNOWLEDGE_IMPORTER, "/knowledge/civilization", "OWNER_DATA_REQUIRED"),
    ("scholar-biographies", "Scholar biographies", KNOWLEDGE_IMPORTER, "/knowledge/scholar", "SOURCE_UNAVAILABLE"),
    ("audio-quran-recitations", "Qur'an recitation audio", "Admin API `POST /quran/admin/recitations` (hosted with checksum, or external link)", "Qur'an reader player, attribution, empty state", "SOURCE_UNAVAILABLE"),
    ("directory-mosques", "Mosques", LISTING_IMPORTER + "; `build_geoalgeria_mosques.py`; `import_osm_mosques.py`", "/directory (search, filters, near me, report)", "PARTIALLY_READY"),
    ("directory-jobs", "Muslim jobs", LISTING_IMPORTER, "/directory, employer, apply link, expiry", "SOURCE_UNAVAILABLE"),
    ("directory-businesses", "Muslim businesses", LISTING_IMPORTER, "/directory", "OWNER_DATA_REQUIRED"),
    ("directory-charities", "Charities", LISTING_IMPORTER, "/directory, no donation links accepted", "SOURCE_UNAVAILABLE"),
    ("directory-professionals", "Muslim professionals", LISTING_IMPORTER, "/directory", "OWNER_DATA_REQUIRED"),
    ("directory-health", "Muslim health services", LISTING_IMPORTER, "/directory", "OWNER_DATA_REQUIRED"),
    ("directory-events", "Islamic events", LISTING_IMPORTER, "/directory, expired events disappear automatically", "OWNER_DATA_REQUIRED"),
    ("directory-organisations", "Islamic organisations and institutions", LISTING_IMPORTER, "/directory", "OWNER_DATA_REQUIRED"),
    ("directory-volunteering", "Volunteering", LISTING_IMPORTER, "/directory", "OWNER_DATA_REQUIRED"),
]


def domain_rows(manifest: dict) -> list[dict]:
    """One row per pending domain. The assigned status must agree with the manifest facts or generation fails."""
    by_id = {d["id"]: d for d in manifest["datasets"]}
    rows = []
    for key, label, importer, frontend, status in DOMAINS:
        d = by_id[key]
        records = d.get("records", 0)
        if status in {"READY", "PARTIALLY_READY"} and not (d["public"] and records > 0 and d["readiness"] == "VERIFIED"):
            raise SystemExit(f"{key}: {status} needs published, verified records")
        if status == "NEEDS_LICENSE" and not (records > 0 and not d["public"] and d["license"]["status"] == "LICENSE_REQUIRED"):
            raise SystemExit(f"{key}: NEEDS_LICENSE needs imported, staged records with licence status LICENSE_REQUIRED")
        if status in {"SOURCE_UNAVAILABLE", "OWNER_DATA_REQUIRED", "NEEDS_PROVENANCE"} and (records > 0 or d["public"]):
            raise SystemExit(f"{key}: {status} cannot have records or be public")
        rows.append({"id": key, "domain": label, "records": records, "source": d["source"]["name"], "license": f"{d['license']['name']} ({d['license']['status']})",
                     "provenance": "recorded per record" if records else "-", "importer": importer, "validation": d.get("validation_status", "NOT_RUN"),
                     "admin": AUDIO_ADMIN if key == "audio-quran-recitations" else ADMIN, "frontend": frontend, "status": status, "action": d["remaining_action"]})
    return rows


def render(manifest: dict) -> str:
    cell = lambda t: str(t if t not in (None, "") else "-").replace("|", "/").replace("\n", " ")
    out = ["# Data readiness", "",
           "Generated from `data/source-manifest.json` by `scripts/generate_data_readiness.py`. Do not edit by hand; edit the manifest and regenerate.",
           f"Manifest as of **{manifest['as_of']}**. Public = visible to visitors in a production deployment after `scripts/sync_manifest.py`.", "",
           "## Domain readiness", "",
           "One row per pending domain. A domain is READY only when every published record has verified provenance and publication rights; "
           "no domain is READY today. Source reachability and licence findings are in [`SOURCE_VERIFICATION.md`](SOURCE_VERIFICATION.md).", ""]
    out += [f"- **{k}** - {v}" for k, v in DOMAIN_STATUSES.items()]
    out += ["", "| Domain | Records | Source | License | Provenance | Importer | Validation | Admin | Frontend | Status | Remaining Action |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in domain_rows(manifest):
        out.append("| " + " | ".join(cell(r[k]) for k in ("domain", "records", "source", "license", "provenance", "importer", "validation", "admin", "frontend")) + f" | **{r['status']}** | {cell(r['action'])} |")
    out += ["", "## Per-source readiness legend", ""]
    out += [f"- **{k}** - {MEANING[k]}" for k in ORDER]
    out += ["", "## Summary", "", "| Readiness | Datasets | Public |", "|---|---|---|"]
    for k in ORDER:
        rows = [d for d in manifest["datasets"] if d["readiness"] == k]
        out.append(f"| {k} | {len(rows)} | {sum(1 for d in rows if d['public'])} |")
    out += ["", "## Every source", "",
            "| Source | Purpose | Licence | Provenance | Verification | Public | Import method | Last checked | Remaining action |", "|---|---|---|---|---|---|---|---|---|"]
    for d in sorted(manifest["datasets"], key=lambda d: (ORDER.index(d["readiness"]), d["id"])):
        lic = f"{d['license']['name']} ({d['license']['status']})"
        src = d["source"]["name"] + (f" {d['source']['version']}" if d["source"].get("version") else "")
        out.append("| " + " | ".join([f"**{d['name']}**<br>`{d['id']}`<br>{cell(src)}", cell(d["purpose"]), cell(lic), cell(d["provenance"]),
                                       cell(f"{d['validation_status']} - {d.get('validation_notes', '')}") + f" **[{d['readiness']}]**",
                                       "yes" if d["public"] else "no", cell(d["import_method"]), d["last_checked"], cell(d["remaining_action"])]) + " |")
    alts = [d for d in manifest["datasets"] if d.get("alternatives_investigated")]
    if alts:
        out += ["", "## Legitimate alternatives investigated", ""]
        for d in alts:
            out.append(f"**{d['name']}**")
            out += [f"- {a}" for a in d["alternatives_investigated"]]
            out.append("")
    out += ["## How a dataset becomes public", "",
            "1. Import it (a script, or an administrator upload to `/api/v1/admin/datasets/{id}/import`).",
            "2. A person checks it and marks it verified (`mark_verified`, with a note).",
            "3. If its licence is not clearly open, the owner records permission (who, when, basis) while publishing.",
            "4. `scripts/sync_manifest.py` (or the admin *Sync manifest* action) applies the decision to readers, search, the assistant and the knowledge graph.", ""]
    return "\n".join(out)


if __name__ == "__main__":
    target = manifest_path().parents[1] / "docs" / "DATA_READINESS.md"
    text = render(load_manifest())
    if "--check" in sys.argv:
        raise SystemExit(0 if target.exists() and target.read_text(encoding="utf-8") == text else 1)
    target.write_text(text, encoding="utf-8")
    print(f"wrote {target}")
