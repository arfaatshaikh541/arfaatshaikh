"""Probe every source target from THIS environment and write data/source-probes.json.

    uv run python scripts/probe_sources.py                 # all targets
    uv run python scripts/probe_sources.py --only wikidata --only openlibrary
    uv run python scripts/probe_sources.py --print         # table only, do not write

Run it on the machine the application will run on: results describe that machine's network, not the internet in general. A reachable
source is not a licensed one; see data/source-candidates.json and the manifest for rights.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.source_probe import probe_all, summarise  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
TARGETS = ROOT / "data" / "probe-targets.json"
OUT = ROOT / "data" / "source-probes.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--print", action="store_true", dest="print_only")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    targets = json.loads(TARGETS.read_text(encoding="utf-8"))["targets"]
    if args.only:
        targets = [t for t in targets if any(o in t["source_id"] for o in args.only)]
    records = probe_all(targets, workers=args.workers)
    for r in records:
        main_req = r["requests"].get("main") or next(iter(r["requests"].values()))
        print(f'{r["source_id"]:34} main={str(main_req["status"] or "-"):>4} lic={r["licence_page_accessible"]!s:5} data={r["data_accessible"]!s:5} '
              f'robots={r["robots"].get("allowed")!s:5} {main_req["error"] or ""}'[:200])
    summary = summarise(records)
    print(json.dumps(summary)[:400])
    if not args.print_only:
        OUT.write_text(json.dumps({"version": 1, "environment_note": "Probed from the build/verification container through the egress proxy; not from the production host.",
                                    "summary": summary, "records": records}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
