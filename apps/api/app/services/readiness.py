"""Domain readiness: the honest, machine-checkable answer to "is this domain ready?".

`data/domain-readiness.json` declares, per domain, a status, the twelve readiness gates (each with evidence) and the blockers.
This module validates that declaration against the source manifest (so it cannot say more than the manifest supports) and
evaluates it against the live database (so the public dashboard can never show a stronger status than the data allows).

READY means every gate is satisfied for the stated scope. It is never implied by an importer existing, by records being
present, or by a dataset being published.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.data_contracts import PUBLISHABLE_LICENCE_STATUSES, can_publish
from app.services.manifest import manifest_path

STATUSES = ("EMPTY", "SOURCE_BLOCKED", "SOURCE_UNVERIFIED", "RIGHTS_UNVERIFIED", "IMPORT_READY", "IMPORTED", "VALIDATED", "PUBLISHED", "READY")
GATES = ("real_source", "provenance_documented", "rights_established", "retrievable_or_present", "schema_maps_without_invention", "validation_passes",
         "duplicates_conflicts_deterministic", "record_level_provenance", "ui_shows_verification_status", "assistant_can_cite", "lifecycle_tests", "actually_verified")
COVERAGE = ("NONE", "PARTIAL", "FULL")
CONFIDENCE = ("none", "low", "medium", "high")
WITH_RECORDS = {"IMPORTED", "VALIDATED", "PUBLISHED", "READY"}
WITHOUT_RECORDS = {"EMPTY", "SOURCE_BLOCKED", "SOURCE_UNVERIFIED", "IMPORT_READY"}
REQUIRED = ("domain", "label", "tier", "status", "coverage", "scope", "source", "source_url", "source_version", "source_type", "licence", "licence_evidence", "attribution",
            "provenance_confidence", "data_quality_confidence", "import_availability", "last_successful_retrieval", "records", "validation_status", "publication_status",
            "blockers", "notes", "gates", "datasets", "published_datasets", "verified_by", "last_verified", "verification_classes")


def registry_path() -> Path:
    return manifest_path().parent / "domain-readiness.json"


def load_registry(path: Path | None = None) -> dict:
    return json.loads((path or registry_path()).read_text(encoding="utf-8"))


def validate_registry(registry: dict, manifest: dict, ledger: dict | None = None) -> list[str]:
    """Every way the declaration claims more than the manifest (or common sense) supports."""
    from app.services.rights_ledger import decision_of, load_ledger, validate_ledger

    ledger = ledger if ledger is not None else load_ledger()
    problems: list[str] = [f"rights ledger: {p}" for p in validate_ledger(ledger, manifest)]
    by_id = {d["id"]: d for d in manifest["datasets"]}
    seen: set[str] = set()
    if tuple(registry.get("statuses", ())) != STATUSES:
        problems.append("registry statuses differ from the code's vocabulary")
    if [g["id"] for g in registry.get("gates", [])] != list(GATES):
        problems.append("registry gate list differs from the code's gates")
    for d in registry.get("domains", []):
        name = d.get("domain", "?")
        where = f"domain {name}"
        if name in seen:
            problems.append(f"{where}: duplicate")
        seen.add(name)
        for key in REQUIRED:
            if key not in d:
                problems.append(f"{where}: missing {key}")
        if any(key not in d for key in REQUIRED):
            continue
        status, records, g = d["status"], d["records"], d["gates"]
        if set(d["verification_classes"]) != {"verified", "imported", "unverified", "assumed", "blocked"}:
            problems.append(f"{where}: verification_classes must have exactly verified, imported, unverified, assumed, blocked")
        if status not in STATUSES:
            problems.append(f"{where}: invalid status {status}")
            continue
        if d["coverage"] not in COVERAGE:
            problems.append(f"{where}: invalid coverage")
        for key in ("provenance_confidence", "data_quality_confidence"):
            if d[key] not in CONFIDENCE:
                problems.append(f"{where}: invalid {key}")
        if set(g) != set(GATES):
            problems.append(f"{where}: gates must be exactly the twelve defined gates")
            continue
        for gate, value in g.items():
            if not isinstance(value.get("passed"), bool) or not str(value.get("evidence") or "").strip():
                problems.append(f"{where}: gate {gate} needs passed (bool) and evidence")
        failing = [gate for gate, value in g.items() if not value.get("passed")]
        if records["total"] != records["published"] + records["hidden"]:
            problems.append(f"{where}: records total != published + hidden")
        for ds in d["datasets"]:
            if ds not in by_id:
                problems.append(f"{where}: dataset {ds} is not in the manifest")
        for ds in d["published_datasets"]:
            entry = by_id.get(ds)
            if entry is None or not entry["public"] or entry["publication_status"] != "published":
                problems.append(f"{where}: published dataset {ds} is not published in the manifest")
        hidden_ok = all(not by_id[ds]["public"] for ds in d["datasets"] if ds in by_id and ds not in d["published_datasets"])
        if not hidden_ok:
            problems.append(f"{where}: a dataset that is public in the manifest is not listed in published_datasets")
        if status == "READY":
            if failing:
                problems.append(f"{where}: READY but gates fail: {', '.join(failing)}")
            if d["blockers"]:
                problems.append(f"{where}: READY must have no blockers")
            if d["coverage"] != "FULL":
                problems.append(f"{where}: READY needs FULL coverage of its stated scope")
            for ds in d["published_datasets"]:
                if decision_of(ledger, ds) != "PUBLISH":
                    problems.append(f"{where}: READY but dataset {ds} has ledger decision {decision_of(ledger, ds)}, not PUBLISH (rights are not unconditionally established)")
                entry = by_id[ds]
                allowed, reasons = can_publish(license_status=entry["license"]["status"], validation_status=entry["validation_status"], rights_confirmation=entry.get("rights_confirmation"))
                if not allowed or entry["license"]["status"] not in PUBLISHABLE_LICENCE_STATUSES:
                    problems.append(f"{where}: READY but dataset {ds} cannot be published: {'; '.join(reasons)}")
        elif not failing and not d["blockers"]:
            problems.append(f"{where}: all gates pass and no blockers, but status is {status}, not READY")
        if status in WITH_RECORDS and records["total"] <= 0:
            problems.append(f"{where}: {status} needs imported records")
        if status in WITHOUT_RECORDS and records["total"] != 0:
            problems.append(f"{where}: {status} cannot have records")
        if status in {"PUBLISHED", "READY"} and records["published"] <= 0:
            problems.append(f"{where}: {status} needs published records")
        if status in {"IMPORTED", "VALIDATED", "RIGHTS_UNVERIFIED"} and records["published"] > 0 and status != "RIGHTS_UNVERIFIED":
            problems.append(f"{where}: {status} means nothing is published")
        if status in {"SOURCE_BLOCKED", "SOURCE_UNVERIFIED", "RIGHTS_UNVERIFIED", "EMPTY"} and status != "EMPTY" and not d["blockers"]:
            problems.append(f"{where}: {status} must state its blockers")
        if status in {"SOURCE_BLOCKED", "SOURCE_UNVERIFIED", "EMPTY"} and g["real_source"]["passed"] and status != "EMPTY":
            problems.append(f"{where}: {status} but the real_source gate passes")
        if status == "EMPTY" and (records["total"] or g["rights_established"]["passed"]):
            problems.append(f"{where}: EMPTY but has records or established rights")
        if d["gates"]["rights_established"]["passed"] is False and d["status"] in {"VALIDATED", "PUBLISHED"} and d["status"] == "VALIDATED":
            problems.append(f"{where}: VALIDATED needs established rights; otherwise use RIGHTS_UNVERIFIED")
        if status == "PUBLISHED" and not g["rights_established"]["passed"]:
            problems.append(f"{where}: PUBLISHED needs established rights; otherwise RIGHTS_UNVERIFIED")
        if d["last_verified"] and date.fromisoformat(d["last_verified"]) > date.fromisoformat(registry["as_of"]):
            problems.append(f"{where}: last_verified is after the registry date")
    return problems


def evaluate_domain(domain: dict, live: dict[str, Any] | None = None) -> dict:
    """The status the public may see: the declared status, lowered if the live data no longer supports it."""
    status = domain["status"]
    live = live or {}
    reasons: list[str] = []
    datasets = live.get("datasets", {})
    if status in {"PUBLISHED", "READY"}:
        for ds in domain["published_datasets"]:
            row = datasets.get(ds)
            if row is None:
                reasons.append(f"dataset {ds} is not registered")
            elif row["publication_status"] != "published" or not row["enabled"]:
                reasons.append(f"dataset {ds} is no longer published")
            elif status == "READY" and (row["validation_status"] != "VERIFIED" or row["license_status"] not in PUBLISHABLE_LICENCE_STATUSES):
                reasons.append(f"dataset {ds} no longer satisfies validation or licence checks")
        if reasons:
            status = "IMPORTED"
    counts = live.get("counts", {}).get(domain["records"]["live_key"])
    if status in {"PUBLISHED", "READY"} and counts is not None and counts["published"] == 0:
        reasons.append("the database holds no published records for this domain")
        status = "EMPTY" if counts["total"] == 0 else "IMPORTED"
    drift = bool(counts) and (counts["total"] != domain["records"]["total"] or counts["published"] != domain["records"]["published"])
    failing = [{"gate": gate, "evidence": value["evidence"]} for gate, value in domain["gates"].items() if not value["passed"]]
    return {"declared_status": domain["status"], "status": status, "downgrade_reasons": reasons, "counts": counts or domain["records"], "registry_out_of_date": drift,
            "why_not_ready": [] if status == "READY" else [{"kind": "blocker", "text": b} for b in domain["blockers"]] + [{"kind": "gate", **f} for f in failing] + [{"kind": "live", "text": r} for r in reasons]}


def summarise(registry: dict, live: dict | None = None) -> dict:
    rows = []
    for d in registry["domains"]:
        evaluated = evaluate_domain(d, live)
        rows.append({k: d[k] for k in ("domain", "label", "tier", "coverage", "scope", "coverage_note", "source", "source_url", "source_version", "source_type", "licence", "licence_evidence", "attribution",
                                        "provenance_confidence", "data_quality_confidence", "import_availability", "importer", "last_successful_retrieval", "validation_status", "publication_status",
                                        "blockers", "notes", "candidates_examined", "verified_by", "last_verified", "verification_classes")} | {"status": evaluated["status"], "declared_status": evaluated["declared_status"],
                    "records": evaluated["counts"], "registry_out_of_date": evaluated["registry_out_of_date"], "why_not_ready": evaluated["why_not_ready"],
                    "gates": d["gates"]})
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    return {"as_of": registry["as_of"], "statuses": registry["statuses"], "status_meaning": registry["status_meaning"], "summary": by_status, "domains": rows}


# ------------------------------------------------------------------ live state (database)
async def live_state(db: AsyncSession) -> dict[str, Any]:
    from app.models.content_contract import DataSet, DirectoryListing, KnowledgeRecord
    from app.models.hadith import HadithNarration
    from app.models.quran import QuranAyah, QuranAyahAudio
    from app.models.tafsir import TafsirEntry
    from app.services.directory import public_filter

    datasets = {d.dataset_key: {"publication_status": d.publication_status, "enabled": d.enabled, "validation_status": d.validation_status, "license_status": d.license_status,
                                "record_count": d.record_count} for d in (await db.scalars(select(DataSet))).all()}
    counts: dict[str, dict] = {}

    async def pair(model, published_col) -> dict:
        total, published = (await db.execute(select(func.count(), func.count().filter(published_col.is_(True))).select_from(model))).one()
        return {"unit": "rows", "total": total, "published": published, "hidden": total - published}
    counts["quran_ayahs"] = await pair(QuranAyah, QuranAyah.published)
    counts["hadith_narrations"] = await pair(HadithNarration, HadithNarration.published)
    counts["tafsir_entries"] = await pair(TafsirEntry, TafsirEntry.published)
    counts["audio"] = await pair(QuranAyahAudio, QuranAyahAudio.published)
    for kind, total, published in (await db.execute(
            select(KnowledgeRecord.entity_type, func.count(), func.count().filter(KnowledgeRecord.dataset_id.in_(
                select(DataSet.id).where(DataSet.publication_status == "published", DataSet.enabled.is_(True))))).group_by(KnowledgeRecord.entity_type))).all():
        counts[f"kr:{kind}"] = {"total": total, "published": published, "hidden": total - published}
    visible = {kind: n for kind, n in (await db.execute(select(DirectoryListing.listing_type, func.count()).where(public_filter()).group_by(DirectoryListing.listing_type))).all()}
    for kind, total in (await db.execute(select(DirectoryListing.listing_type, func.count()).group_by(DirectoryListing.listing_type))).all():
        counts[f"dl:{kind}"] = {"total": total, "published": visible.get(kind, 0), "hidden": total - visible.get(kind, 0)}
    for key in ("fiqh", "aqeedah", "seerah", "scholar", "terminology", "history", "civilization", "library_work", "hadith_grading"):
        counts.setdefault(f"kr:{key}", {"total": 0, "published": 0, "hidden": 0})
    for key in ("organisation", "event", "charity", "volunteering", "business", "professional", "health", "job", "mosque"):
        counts.setdefault(f"dl:{key}", {"total": 0, "published": 0, "hidden": 0})
    return {"datasets": datasets, "counts": counts}
