"""Regenerate docs/PENDING_DATA_AUDIT.md from data/domain-readiness.json (per-domain facts) plus the audit narrative below.

    uv run python scripts/generate_pending_data_audit.py          # write
    uv run python scripts/generate_pending_data_audit.py --check  # exit 1 if stale
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.manifest import manifest_path  # noqa: E402
from app.services.readiness import load_registry  # noqa: E402

# Claims made by the previous report, and what was done to check each one on 2026-10-01.
CLAIMS = [
    ("668 API unit/contract tests pass", "Re-ran `pytest --ignore=tests/integration` on the restored environment before changing anything", "CONFIRMED: 668 passed"),
    ("19,781 mosque listings, 19,776 visible, 5 duplicates hidden", "SQL counts on the working database", "CONFIRMED"),
    ("21,185 hadith gradings / 67,681 grader entries, hidden", "SQL counts; public `/knowledge/records` returned 0 for the type", "CONFIRMED (hidden)"),
    ("13 validation rules pass", "Ran `scripts/validate_data.py` on the populated database", "CONFIRMED (now 14 rules after this pass)"),
    ("Admin preview, unpublish, provenance/history exist", "Read `datasets_admin.py` and `admin-data-panel.tsx`", "CONFIRMED in code; the screens had NOT been clicked through (done in this pass)"),
    ("Browser checks passed on the production stack", "The report said development server only", "CONFIRMED as a limitation: production Docker/nginx verification had not been done (done in this pass)"),
    ("Hadith gradings: Zubair Ali Za'i's references are 'named' in References.md", "Re-read References.md", "CONFIRMED: the file names zubairalizai.com with no page"),
    ("Mosque anomaly: one former synagogue", "Keyword scan of every imported name", "INCOMPLETE: the scan found 7 more records with 'Chapel'/'Temple' in their names (see `data/source-quality-notes.json`); cause unknown"),
    ("Domain status vocabulary (READY, PARTIALLY_READY, ...)", "Compared with the requested vocabulary", "REPLACED by EMPTY ... READY with twelve gates (`data/domain-readiness.json`)"),
    ("Imports 'record the source version'", "Read `DataSetImport`", "NOT TRUE before this pass: only a file hash was stored. Migration 0087 adds adapter, source version, retrieval time and checksum"),
]

SCHEMA = {
    "kr": "`knowledge_records` with source-level provenance (migration 0086: work, edition, volume, page, chapter, language, publication/licence/provenance status, per-type `attributes`).",
    "dl": "`directory_listings` with per-type `attributes`, expiry and start/end times (migration 0086).",
    "quran": "`quran_*` tables with source passages and checksums.",
    "hadith": "`hadith_*` tables with source passages and checksums.",
    "tafsir": "`tafsir_*` tables with source passages.",
    "audio": "`quran_recitation_editions` (hosted or external link, licence, authorisation, caching/offline flags) and `quran_ayah_audio`.",
}


def render(registry: dict) -> str:
    out = ["# Pending data audit", "",
           "Audit of every domain against the actual repository and database on **" + registry["as_of"] + "**, repeated at the start of the readiness pass. "
           "It does not trust the previous report: each claim below was checked.", "",
           "Statuses use the readiness vocabulary of [`DATA_READINESS.md`](DATA_READINESS.md); sources and licences are in [`SOURCE_VERIFICATION.md`](SOURCE_VERIFICATION.md). "
           "No human scholarly or legal review has taken place for any domain.", "",
           "## Claims of the previous report, checked", "", "| Claim | How it was checked | Result |", "|---|---|---|"]
    out += [f"| {a} | {b} | {c} |" for a, b, c in CLAIMS]
    out += ["", "## What exists", "",
            "- **Migrations**: 87 (head `20261001_0087`): 0084 data contract and directories, 0085 Arabic full text, 0086 provenance and per-type structure, 0087 import source versions.",
            "- **Source registry**: `Source` > `SourceEdition` (publisher, language, ISBN, licence) > acquisition > integrity > review > attribution > retrieval gate; claims with dispute notes; `data/source-manifest.json`; `data/source-candidates.json`; `data/domain-readiness.json`.",
            "- **Importers**: source adapters in `app/importers` (GeoAlgeria mosques, hadith-api gradings, OpenStreetMap Overpass) run by `scripts/run_importer.py` or *Data & trust > Importers*; the contract importers `import_knowledge_records.py` / `import_directory.py`; the older Qur'an, hadith, tafsir and translation importers.",
            "- **Admin**: readiness (why not READY), importers (probe, preview, run), datasets (preview, verify, publish, unpublish, provenance and import history with source versions, conflicts, rollback), directory moderation, reports, assistant answers, audit log.",
            "- **Quality**: `scripts/validate_data.py` (14 rules), `scripts/data_quality_report.py` ([`DATA_QUALITY_REPORT.md`](DATA_QUALITY_REPORT.md)), conflict detection (`app/services/data_quality.py`), `data/source-quality-notes.json`.",
            "- **Assistant**: retrieves approved Qur'an/hadith/tafsir evidence and published knowledge records; every item carries an authority class, verification state, source, edition, record id and URL; it abstains without a sufficient source.", "",
            "## Per domain", ""]
    for d in registry["domains"]:
        key = d["records"]["live_key"]
        schema = SCHEMA["kr"] if key.startswith("kr:") else SCHEMA["dl"] if key.startswith("dl:") else SCHEMA["quran"] if key == "quran_ayahs" else SCHEMA["hadith"] if key == "hadith_narrations" else SCHEMA["tafsir"] if key == "tafsir_entries" else SCHEMA["audio"]
        r = d["records"]
        out += [f"### {d['label']}", "",
                f"- **DOMAIN**: {d['label']} (`{d['domain']}`, tier {d['tier']})",
                f"- **STATUS**: {d['status']} ({d['coverage']} coverage)",
                f"- **CURRENT_SCHEMA**: {schema}",
                f"- **IMPORTER**: {d['importer'] or d['import_availability']}",
                "- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)",
                "- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`",
                f"- **CURRENT_DATA_COUNT**: {r['total']} {r['unit']} ({r['published']} published, {r['hidden']} hidden)",
                f"- **CURRENT_SOURCE**: {d['source'] or 'none acquired'}" + (f" ({d['source_version']})" if d.get("source_version") else ""),
                f"- **LICENCE**: {d['licence'] or 'not applicable'}",
                f"- **BLOCKER**: {'; '.join(d['blockers']) if d['blockers'] else 'none'}",
                f"- **CANDIDATES EXAMINED**: {', '.join(d['candidates_examined']) if d['candidates_examined'] else 'see the manifest entry'}",
                f"- **NEXT_ACTION**: {'Owner supplies an authorised dataset, or a legitimate source is found and its adapter written.' if d['status'] in ('EMPTY',) else 'Resolve the blockers above.' if d['blockers'] else 'None.'}", ""]
    out += ["## Gaps found and closed in this pass", "",
            "1. No machine-readable domain readiness: added `data/domain-readiness.json`, twelve gates, a validator, a live evaluator that lowers a status the data no longer supports, `/knowledge/domains`, an admin view with the reason for every non-READY domain, and an honest public dashboard.",
            "2. Importers were ad-hoc scripts: replaced by a source-adapter architecture with probes, preview, all-or-nothing runs, version and checksum recording, and safe re-runs.",
            "3. Hadith grade entries had no place for the grading work, edition, page, rights or verification state: added (all optional, never inferred), keeping each grader separate.",
            "4. Mosque data lacked source identifiers in a first-class place, coverage statements, and conflict reports: added the GeoAlgeria id, a coverage endpoint and UI statement, and duplicate/similar/co-located/non-mosque-name candidates (reported, never corrected).",
            "5. The assistant treated every record alike: every cited item now carries an authority class and verification state.",
            "6. No data-quality report and no Arabic review list: added both.",
            "7. The admin screens had not been exercised in a browser and production Docker/nginx verification had not been done: see the final report for what was and was not verified.", ""]
    return "\n".join(out)


if __name__ == "__main__":
    target = manifest_path().parents[1] / "docs" / "PENDING_DATA_AUDIT.md"
    text = render(load_registry())
    if "--check" in sys.argv:
        raise SystemExit(0 if target.exists() and target.read_text(encoding="utf-8") == text else 1)
    target.write_text(text, encoding="utf-8")
    print(f"wrote {target}")
