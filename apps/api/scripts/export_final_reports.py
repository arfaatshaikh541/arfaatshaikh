"""Write the three final machine-readable reports at the repository root, from the registry, manifest, rights ledger, probes and live database counts.

    uv run python scripts/export_final_reports.py --api-tests "757 passed" --web-tests "43 passed"

DATA_READINESS_FINAL.json      every domain with status, counts, gates, blockers, rights decisions, plus the production verdict and acceptance criteria
SOURCE_VERIFICATION_FINAL.json every dataset (licence, rights decision, evidence), every candidate source with its probe result, rejected sources
DATA_COVERAGE_FINAL.json       where each domain actually has data (GLOBAL / <COUNTRY>_ONLY / HIDDEN_PENDING_RIGHTS / NO_VERIFIED_DATA)
Nothing here is computed optimistically: a criterion that cannot be shown to pass is reported as FAIL or NOT_VERIFIED.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.models.content_contract import DirectoryListing  # noqa: E402
from app.services.coverage import build_coverage  # noqa: E402
from app.services.directory import public_filter  # noqa: E402
from app.services.manifest import load_manifest, manifest_path  # noqa: E402
from app.services.readiness import live_state, load_registry, summarise  # noqa: E402
from app.services.rights_ledger import load_ledger  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
AS_OF = "2026-10-03"


def criteria(verification: dict, tests: dict, summary: dict, ledger: dict) -> list[dict]:
    caveated = [k for k, v in ledger["datasets"].items() if v["decision"] == "PUBLISH_WITH_CAVEAT"]
    browser = verification["browser_suites"]
    ok = lambda b: "PASS" if b else "FAIL"  # noqa: E731
    return [
        {"criterion": "production build succeeds", "result": "PASS", "evidence": "next build exit 0; api, web, migrate and worker images built from the real Dockerfiles (CA injected into builder stages only)"},
        {"criterion": "migrations succeed", "result": "PASS", "evidence": "alembic up/down/up to 20261003_0088 on a scratch database; the stack's migrate service completed"},
        {"criterion": "all tests pass", "result": ok(tests["api_failed"] == 0 and tests["web_failed"] == 0), "evidence": f"API {tests['api']}; web {tests['web']}; typecheck and ESLint clean"},
        {"criterion": "security checks pass", "result": "PASS_AUTOMATED_ONLY", "evidence": "pip-audit and pnpm audit clean; secret scan found placeholders only; CORS, CSRF, authn/authz, injection, upload, SSRF and rate-limit checks passed. No external penetration test."},
        {"criterion": "real production compose is tested", "result": "FAIL", "evidence": "docker-compose.prod.yml was run, but MinIO and its init job could not be started (quay.io answers 403), so the complete file was not run"},
        {"criterion": "required services are tested", "result": "FAIL", "evidence": "MinIO not run; Ollama has no model (pull failed); the worker registers no tasks; the backup job was exercised only against an empty database"},
        {"criterion": "frontend works under /worldofislam", "result": ok(browser["browser-verify.cjs"]["failed"] == 0 and browser["prod-extra-verify.cjs"]["failed"] == 0),
         "evidence": f"{browser['browser-verify.cjs']['passed']} + {browser['prod-extra-verify.cjs']['passed']} browser checks passed on the stack (local hosts mapping and self-signed certificate, not app.arfaat.com)"},
        {"criterion": "AI works or clearly reports unavailable", "result": "PASS", "evidence": "no model is installed; the API reports ai_synthesis.status = unavailable and still returns cited, quoted evidence"},
        {"criterion": "every published dataset has provenance", "result": "PASS", "evidence": "scripts/validate_data.py 14/14 on the working database"},
        {"criterion": "every published dataset has appropriate rights status", "result": "FAIL", "evidence": f"{len(caveated)} published datasets rest on PUBLISH_WITH_CAVEAT, not on established rights: {', '.join(caveated)}"},
        {"criterion": "geographic coverage is explicit", "result": "PASS", "evidence": "GET /knowledge/coverage and the status page state the countries; mosques are ALGERIA_ONLY"},
        {"criterion": "religious claims are source-backed", "result": "PASS", "evidence": "every cited passage carries source, licence and authority class; with no source the assistant abstains"},
        {"criterion": "hadith grades are attributed", "result": "NOT_APPLICABLE", "evidence": "no hadith grade is published; the structure stores each grader separately and never picks a winner"},
        {"criterion": "scholarly disagreement is preserved", "result": "PASS_STRUCTURE_ONLY", "evidence": "fiqh/aqeedah records are per madhhab/school and listed separately (tested); no such records exist yet"},
        {"criterion": "no fabricated records exist", "result": "NOT_VERIFIED", "evidence": "every imported record comes from a named source with a checksum; absence of fabrication is not independently proven and no human reviewed the data"},
        {"criterion": "no fake directories exist", "result": "PASS", "evidence": "the only listings are 19,781 imported mosque records (Algeria); test fixtures are rolled back"},
        {"criterion": "no fake audio exists", "result": "PASS", "evidence": "no recitation is published; delivery classes require recorded rights"},
        {"criterion": "no fake citations exist", "result": "PASS", "evidence": "citation validation rejects references that are not in the retrieved evidence (tests)"},
        {"criterion": "domains READY", "result": "FAIL", "evidence": f"status counts: {summary['summary']}; no domain is READY"},
    ]


BLOCKERS = [
    "Complete docker-compose.prod.yml not run: quay.io (MinIO, mc) answers 403 from the build environment.",
    "Production host https://app.arfaat.com was not tested; all browser checks ran against a local copy with a self-signed certificate.",
    "Rights are not established for published Qur'an text, tajweed, the two translations and the mosque data (PUBLISH_WITH_CAVEAT); hadith text, hadith grades and tafsir are hidden for the same reason.",
    "Every candidate source host except PyPI, npm and raw.githubusercontent.com is refused by this environment's network policy (Wikidata, OpenStreetMap/Overpass, Open Library, Internet Archive, Gutenberg, charity registers, job APIs, recitation hosts, sunnah.com).",
    "Fiqh, aqeedah, seerah, terminology, history, civilization, organisations, events, volunteering, businesses, professionals and health have no data and no legitimate source found.",
    "No human has reviewed any Arabic string, any scholarly content or any legal question; 168 Arabic strings await a native reader.",
    "No Ollama model is installed; the AI synthesis is unavailable.",
    "The worker registers no Celery tasks; the backup job has not been tested against real data.",
]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-tests", required=True)
    ap.add_argument("--web-tests", required=True)
    args = ap.parse_args()
    tests = {"api": args.api_tests, "web": args.web_tests, "api_failed": 0 if " failed" not in args.api_tests else 1, "web_failed": 0 if " failed" not in args.web_tests else 1}
    data_dir = manifest_path().parent
    verification = json.loads((data_dir / "verification-prod-compose.json").read_text(encoding="utf-8"))
    registry, manifest, ledger = load_registry(), load_manifest(), load_ledger()
    db = Database(get_settings())
    async with db.session_factory() as session:
        live = await live_state(session)
        rows = (await session.execute(select(DirectoryListing.listing_type, DirectoryListing.country, func.count(), func.count(DirectoryListing.city), func.count(func.distinct(DirectoryListing.region)))
                                      .where(public_filter(), DirectoryListing.country.is_not(None)).group_by(DirectoryListing.listing_type, DirectoryListing.country))).all()
    await db.dispose()
    summary = summarise(registry, live)
    by_dataset = {d["id"]: d for d in manifest["datasets"]}
    domains = []
    for d in summary["domains"]:
        reg = next(x for x in registry["domains"] if x["domain"] == d["domain"])
        domains.append({"domain": d["domain"], "label": d["label"], "tier": d["tier"], "status": d["status"], "coverage": d["coverage"], "scope": d["scope"], "source": d["source"], "licence": d["licence"],
                        "records": d["records"], "validation_status": d["validation_status"], "blockers": d["blockers"], "gates_not_met": [g for g, v in d["gates"].items() if not v["passed"]],
                        "datasets": [{"id": ds, "public": by_dataset[ds]["public"], "rights_decision": (ledger["datasets"].get(ds) or {}).get("decision", "NO_LEDGER_ENTRY")} for ds in reg["datasets"]],
                        "evidence_classes": d["verification_classes"], "verified_by": d["verified_by"]})
    readiness = {"as_of": AS_OF, "production_verdict": "NOT_PRODUCTION_READY", "blockers": BLOCKERS, "acceptance_criteria": criteria(verification, tests, summary, ledger),
                 "status_counts": summary["summary"], "tests": tests, "domains": domains,
                 "note": "Automated checks only. No human scholarly, native-language or legal review has taken place."}
    (ROOT / "DATA_READINESS_FINAL.json").write_text(json.dumps(readiness, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    candidates = json.loads((data_dir / "source-candidates.json").read_text(encoding="utf-8"))
    probes = json.loads((data_dir / "source-probes.json").read_text(encoding="utf-8"))
    tafsir = json.loads((data_dir / "rights-ledger-tafsir.json").read_text(encoding="utf-8"))
    grades = json.loads((data_dir / "rights-ledger-hadith-gradings.json").read_text(encoding="utf-8"))
    sources = {"as_of": AS_OF,
               "datasets": [{"id": d["id"], "name": d["name"], "source": d["source"], "licence": d["license"], "validation_status": d["validation_status"], "public": d["public"],
                             "rights_ledger": ledger["datasets"].get(d["id"]), "remaining_action": d.get("remaining_action")} for d in manifest["datasets"]],
               "candidate_sources": [{k: c.get(k) for k in ("SOURCE_ID", "SOURCE_NAME", "SOURCE_URL", "DATA_DOMAIN", "LICENSE", "LICENSE_URL", "VERIFICATION_STATUS", "REDISTRIBUTION_ALLOWED", "PROBE_RESULT", "LAST_PROBED", "NOTES")} for c in candidates["sources"]],
               "rejected_and_unresolved": [c["SOURCE_ID"] for c in candidates["sources"] if c["VERIFICATION_STATUS"] in ("PROVENANCE_UNCLEAR", "NOT_ALLOWED_FOR_REDISTRIBUTION", "LICENSE_REQUIRED")],
               "probes": {"environment_note": probes["environment_note"], "summary": probes["summary"], "records": [{k: r[k] for k in ("source_id", "domain", "host", "last_checked", "dns", "accessible", "licence_page_accessible", "terms_accessible", "data_accessible", "importer_available")} | {"main_status": (r["requests"].get("main") or {}).get("status"), "main_error": (r["requests"].get("main") or {}).get("error")} for r in probes["records"]]},
               "companion_ledgers": {"tafsir_editions": {"count": tafsir["counts"]["editions"], "finding": tafsir["finding"], "upstream_sha256": tafsir["upstream_sha256"]},
                                     "hadith_graders": {"totals": grades["totals"], "finding": grades["finding"], "upstream_sha256": grades["upstream_sha256"]}}}
    (ROOT / "SOURCE_VERIFICATION_FINAL.json").write_text(json.dumps(sources, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    coverage = build_coverage(summary["domains"], [{"type": t, "country": c, "published": int(n), "city_known": int(ck), "regions": int(rg)} for t, c, n, ck, rg in rows])
    coverage["as_of"] = AS_OF
    (ROOT / "DATA_COVERAGE_FINAL.json").write_text(json.dumps(coverage, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote DATA_READINESS_FINAL.json, SOURCE_VERIFICATION_FINAL.json, DATA_COVERAGE_FINAL.json;", summary["summary"])


if __name__ == "__main__":
    asyncio.run(main())
