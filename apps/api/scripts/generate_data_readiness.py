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


def render(manifest: dict) -> str:
    out = ["# Data readiness", "",
           "Generated from `data/source-manifest.json` by `scripts/generate_data_readiness.py`. Do not edit by hand; edit the manifest and regenerate.",
           f"Manifest as of **{manifest['as_of']}**. Public = visible to visitors in a production deployment after `scripts/sync_manifest.py`.", "",
           "## Status legend", ""]
    out += [f"- **{k}** - {MEANING[k]}" for k in ORDER]
    out += ["", "## Summary", "", "| Readiness | Datasets | Public |", "|---|---|---|"]
    for k in ORDER:
        rows = [d for d in manifest["datasets"] if d["readiness"] == k]
        out.append(f"| {k} | {len(rows)} | {sum(1 for d in rows if d['public'])} |")
    out += ["", "## Every source", "",
            "| Source | Purpose | Licence | Provenance | Verification | Public | Import method | Last checked | Remaining action |", "|---|---|---|---|---|---|---|---|---|"]
    cell = lambda t: str(t or "-").replace("|", "/").replace("\n", " ")
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
