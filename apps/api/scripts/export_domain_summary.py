"""Write data/domain-summary.json: the final machine-readable summary of every domain, using live database counts.

    uv run python scripts/export_domain_summary.py

Fields follow the completion report: DOMAIN, STATUS, SOURCE, LICENCE, RECORD COUNT, PUBLISHED, HIDDEN, VALIDATION, PROVENANCE,
BLOCKER, VERIFIED BY, plus the five evidence classes (verified, imported, unverified, assumed, blocked) kept apart.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.services.manifest import manifest_path  # noqa: E402
from app.services.readiness import live_state, load_registry, summarise  # noqa: E402


async def main() -> None:
    db = Database(get_settings())
    async with db.session_factory() as session:
        live = await live_state(session)
    await db.dispose()
    summary = summarise(load_registry(), live)
    rows = [{"DOMAIN": d["label"], "STATUS": d["status"], "COVERAGE": d["coverage"], "SOURCE": d["source"], "LICENCE": d["licence"], "RECORD_COUNT": d["records"]["total"],
             "PUBLISHED": d["records"]["published"], "HIDDEN": d["records"]["hidden"], "VALIDATION": d["validation_status"],
             "PROVENANCE": f"confidence {d['provenance_confidence']}; " + ("recorded per record" if d["records"]["total"] else "no records"),
             "BLOCKER": d["blockers"], "VERIFIED_BY": d["verified_by"], "GATES_NOT_MET": [g for g, v in d["gates"].items() if not v["passed"]],
             "EVIDENCE": next(x for x in load_registry()["domains"] if x["domain"] == d["domain"])["verification_classes"]} for d in summary["domains"]]
    out = {"generated_for": "World of Islam", "as_of": summary["as_of"], "status_counts": summary["summary"], "domains": rows}
    target = manifest_path().parent / "domain-summary.json"
    target.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {target}: {summary['summary']}")


if __name__ == "__main__":
    asyncio.run(main())
