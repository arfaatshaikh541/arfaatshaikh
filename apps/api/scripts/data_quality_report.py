"""Data-quality report over the live database: per-domain counts, unverified/hidden/expired, missing metadata, invalid URLs,
orphans, duplicates and conflicts, coverage by country. Reports problems; repairs nothing.

    uv run python scripts/data_quality_report.py                      # JSON to stdout
    uv run python scripts/data_quality_report.py --markdown docs/DATA_QUALITY_REPORT.md
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.services.data_quality import quality_report  # noqa: E402


def to_markdown(report: dict) -> str:
    out = ["# Data quality report", "", f"Generated {report['generated_at']} by `scripts/data_quality_report.py` from the live database. It reports problems and repairs nothing.", "",
           "## Records per domain", "", "| Source of count | Total | Published (visible) | Hidden |", "|---|---|---|---|"]
    out += [f"| `{k}` | {v['total']} | {v['published']} | {v['hidden']} |" for k, v in report["domains"].items() if v["total"]]
    for title, key in (("Knowledge records", "knowledge_records"), ("Directory listings", "directory_listings")):
        out += ["", f"## {title}", "", "| Measure | Count |", "|---|---|"] + [f"| {k.replace('_', ' ')} | {v} |" for k, v in report[key].items()]
    out += ["", "## Duplicates and conflicts (candidates for human review)", "", "| Kind | Count |", "|---|---|"] + [f"| {k.replace('_', ' ')} | {v} |" for k, v in report["conflicts"]["totals"].items()]
    out += ["", "## Coverage of visible listings (country:type)", "", "| Country:type | Visible listings |", "|---|---|"] + [f"| {k} | {v} |" for k, v in report["coverage"].items()]
    out += ["", "## Source-quality notes (retained unchanged)", ""]
    out += [f"- `{n['record_key']}` ({n['dataset']}): {n['observation']} Unknown: {n['unknown']} Action: {n['action']}. Record still present: {n['record_present']}." for n in report["source_quality_notes"]] or ["None."]
    return "\n".join(out) + "\n"


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--markdown")
    args = ap.parse_args()
    db = Database(get_settings())
    async with db.session_factory() as session:
        report = await quality_report(session)
    await db.dispose()
    if args.markdown:
        Path(args.markdown).write_text(to_markdown(report), encoding="utf-8")
        print(f"wrote {args.markdown}")
    else:
        print(json.dumps(report, indent=1, default=str, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
