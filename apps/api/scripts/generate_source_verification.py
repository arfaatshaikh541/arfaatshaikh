"""Regenerate docs/SOURCE_VERIFICATION.md from data/source-candidates.json and data/source-manifest.json.

    uv run python scripts/generate_source_verification.py          # write
    uv run python scripts/generate_source_verification.py --check  # exit 1 if the file is out of date

A source is VERIFIED only when its licence text and provenance were actually read; nothing moves from pending to verified
without an edit to data/source-candidates.json (reviewed in version control) or, for a stored dataset, an audited
`mark_verified` action with a note.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.manifest import load_manifest, manifest_path  # noqa: E402

MEANING = {
    "VERIFIED": "Licence text and provenance were read and permit the stated use.",
    "NEEDS_MANUAL_REVIEW": "Looked at, but a person must decide (or the owner must supply the data).",
    "LICENSE_REQUIRED": "The data is real but the right to publish it is not established.",
    "PROVENANCE_UNCLEAR": "The upstream origin or the licence could not be established.",
    "TECHNICALLY_UNAVAILABLE": "A legitimate source, but it could not be reached or accessed from the build environment.",
    "NOT_ALLOWED_FOR_REDISTRIBUTION": "The terms forbid redistribution.",
}
FROM_READINESS = {"VERIFIED": "VERIFIED", "NEEDS_REVIEW": "NEEDS_MANUAL_REVIEW", "LICENSE_REQUIRED": "LICENSE_REQUIRED", "PROVENANCE_UNCLEAR": "PROVENANCE_UNCLEAR", "UNAVAILABLE": "TECHNICALLY_UNAVAILABLE"}
FIELDS = ("SOURCE_NAME", "SOURCE_URL", "OWNER", "TYPE", "DATA_DOMAIN", "LICENSE", "LICENSE_URL", "PROVENANCE", "ACCESS_METHOD", "REDISTRIBUTION_ALLOWED",
          "COMMERCIAL_USE_ALLOWED", "ATTRIBUTION_REQUIRED", "LAST_VERIFIED", "VERIFICATION_STATUS")


def render(candidates: dict, manifest: dict) -> str:
    cell = lambda t: str(t if t not in (None, "") else "-").replace("|", "/").replace("\n", " ")
    sources = candidates["sources"]
    out = ["# Source verification", "",
           "Generated from `data/source-candidates.json` (candidates examined for the pending domains) and `data/source-manifest.json` (datasets already stored) by "
           "`scripts/generate_source_verification.py`. Edit the JSON, not this file.", "",
           "A source is **VERIFIED** only when its licence text and provenance were read. Nothing becomes verified silently: a candidate changes status only by an edit to "
           "`data/source-candidates.json` that is reviewed in version control, and a stored dataset only through the audited `mark_verified` action (with a note) in *Data & trust*.", "",
           "## Status legend", ""]
    out += [f"- **{k}** - {v}" for k, v in MEANING.items()]
    out += ["", "## Summary", "", "| Status | Candidates examined |", "|---|---|"]
    out += [f"| {k} | {sum(1 for s in sources if s['VERIFICATION_STATUS'] == k)} |" for k in MEANING]
    out += ["", "## Candidates examined for the pending domains", "",
            "Last verified " + candidates["as_of"] + ". Hosts marked TECHNICALLY_UNAVAILABLE returned no response from the build environment on that date; that says nothing against their licences.", ""]
    for s in sorted(sources, key=lambda s: (list(MEANING).index(s["VERIFICATION_STATUS"]), s["SOURCE_ID"])):
        out += [f"### {s['SOURCE_NAME']} - {s['VERIFICATION_STATUS']}", "", f"`{s['SOURCE_ID']}`" + (f" - backs dataset `{s['MANIFEST_DATASET']}`" if s.get("MANIFEST_DATASET") else ""), ""]
        out += [f"- **{k}**: {cell(s[k])}" for k in FIELDS]
        if s.get("NOTES"):
            out.append(f"- **NOTES**: {cell(s['NOTES'])}")
        out.append("")
    out += ["## Datasets already stored (from the manifest)", "",
            "| Dataset | Source | Licence | Verification status | Public |", "|---|---|---|---|---|"]
    for d in manifest["datasets"]:
        status = FROM_READINESS.get(d["readiness"])
        if status is None:
            continue
        out.append(f"| `{d['id']}` | {cell(d['source']['name'])} | {cell(d['license']['name'])} ({d['license']['status']}) | {status} | {'yes' if d['public'] else 'no'} |")
    owners = [d['id'] for d in manifest["datasets"] if d["readiness"] == "OWNER_UPLOAD_REQUIRED"]
    out += ["", f"No source of any kind exists yet for {len(owners)} datasets (`" + "`, `".join(owners) + "`). They are not listed above because there is nothing to verify; they need owner-supplied data.", ""]
    return "\n".join(out)


if __name__ == "__main__":
    data = manifest_path().parent
    text = render(json.loads((data / "source-candidates.json").read_text(encoding="utf-8")), load_manifest())
    target = data.parent / "docs" / "SOURCE_VERIFICATION.md"
    if "--check" in sys.argv:
        raise SystemExit(0 if target.exists() and target.read_text(encoding="utf-8") == text else 1)
    target.write_text(text, encoding="utf-8")
    print(f"wrote {target}")
