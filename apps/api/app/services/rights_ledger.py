"""The rights ledger: for each dataset, what is known about the rights to redistribute it, with the evidence and the open questions.

A ledger entry never grants permission by itself. It records a determination and the evidence behind it, and the checks below tie it to
the manifest: nothing public without a PUBLISH or PUBLISH_WITH_CAVEAT entry, nothing KEEP_HIDDEN public, and a domain is READY only if every
dataset it publishes has an unqualified PUBLISH.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.services.manifest import manifest_path

DECISIONS = ("PUBLISH", "PUBLISH_WITH_CAVEAT", "KEEP_HIDDEN")
REDISTRIBUTION = ("ESTABLISHED", "CAVEATED", "NOT_ESTABLISHED")
REQUIRED = ("original_work_public_domain", "digital_edition_rights", "packager_rights", "translation_rights", "redistribution_allowed", "decision", "evidence", "open_questions", "determined_on", "determined_by")
COMPANIONS = {"rights-ledger-tafsir.json": ("editions", ("tafsir-arabic-classical", "tafsir-arabic-modern", "tafsir-english")),
              "rights-ledger-hadith-gradings.json": ("graders", ("hadith-grading",))}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def ledger_path() -> Path:
    return manifest_path().parent / "rights-ledger.json"


def load_ledger(path: Path | None = None) -> dict:
    return json.loads((path or ledger_path()).read_text(encoding="utf-8"))


def decision_of(ledger: dict | None, dataset_id: str) -> str | None:
    return ((ledger or {}).get("datasets", {}).get(dataset_id) or {}).get("decision")


def validate_ledger(ledger: dict, manifest: dict, data_dir: Path | None = None) -> list[str]:
    problems: list[str] = []
    by_id = {d["id"]: d for d in manifest["datasets"]}
    entries = ledger.get("datasets", {})
    for ident, e in entries.items():
        where = f"ledger {ident}"
        if ident not in by_id:
            problems.append(f"{where}: not in the manifest")
        missing = [k for k in REQUIRED if k not in e]
        if missing:
            problems.append(f"{where}: missing {', '.join(missing)}")
            continue
        if e["decision"] not in DECISIONS:
            problems.append(f"{where}: invalid decision")
        if e["redistribution_allowed"] not in REDISTRIBUTION:
            problems.append(f"{where}: invalid redistribution_allowed")
        if not DATE.match(str(e["determined_on"])):
            problems.append(f"{where}: determined_on must be YYYY-MM-DD")
        if "review" not in str(e["determined_by"]).lower() or "no human" not in str(e["determined_by"]).lower():
            problems.append(f"{where}: determined_by must say that no human or legal review took place unless one is recorded")
        if e["decision"] == "PUBLISH" and e["redistribution_allowed"] != "ESTABLISHED":
            problems.append(f"{where}: PUBLISH needs redistribution_allowed ESTABLISHED")
        if e["decision"] == "PUBLISH_WITH_CAVEAT" and (e["redistribution_allowed"] != "CAVEATED" or not e["open_questions"]):
            problems.append(f"{where}: PUBLISH_WITH_CAVEAT needs CAVEATED and the open questions stated")
        if e["decision"] == "KEEP_HIDDEN" and e["redistribution_allowed"] == "ESTABLISHED":
            problems.append(f"{where}: KEEP_HIDDEN contradicts ESTABLISHED redistribution")
        if not e["evidence"]:
            problems.append(f"{where}: needs at least one evidence entry")
        for item in e["evidence"]:
            if not (item.get("claim") and str(item.get("url", "")).startswith("https://") and DATE.match(str(item.get("retrieved", "")))):
                problems.append(f"{where}: every evidence entry needs claim, https url and retrieved date")
        if e["decision"] == "KEEP_HIDDEN" and ident in by_id and by_id[ident]["public"]:
            problems.append(f"{where}: KEEP_HIDDEN but the manifest publishes it")
    for ident, d in by_id.items():
        if d["public"] and decision_of(ledger, ident) not in ("PUBLISH", "PUBLISH_WITH_CAVEAT"):
            problems.append(f"manifest {ident}: public without a PUBLISH or PUBLISH_WITH_CAVEAT ledger entry")
    folder = data_dir or manifest_path().parent
    for name, (rows_key, datasets) in COMPANIONS.items():
        path = folder / name
        if not path.exists():
            problems.append(f"companion ledger {name} is missing")
            continue
        rows = json.loads(path.read_text(encoding="utf-8")).get(rows_key, [])
        if not rows or any(r.get("decision") != "KEEP_HIDDEN" or r.get("redistribution_allowed", r.get("grading_rights")) != "NOT_ESTABLISHED" for r in rows):
            problems.append(f"companion ledger {name}: every row must be KEEP_HIDDEN / NOT_ESTABLISHED until evidence is recorded")
        for ds in datasets:
            if ds in by_id and by_id[ds]["public"]:
                problems.append(f"{name}: dataset {ds} is public although its ledger rows are KEEP_HIDDEN")
    return problems
