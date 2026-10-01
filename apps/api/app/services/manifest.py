"""Loads and validates data/source-manifest.json, the single declaration of every dataset's source, licence,
provenance, validation and publication state."""
from __future__ import annotations

import json
import os
from pathlib import Path

from app.services.data_contracts import PUBLISHABLE_LICENCE_STATUSES, can_publish

LICENSE = ("VERIFIED_OPEN", "PUBLIC_DOMAIN", "PD_WORK_OPEN_EDITION_DECLARED", "OWNER_PERMISSION_GRANTED", "LICENSE_REQUIRED", "PROVENANCE_UNCLEAR", "UNKNOWN")
VALIDATION = ("VERIFIED", "NEEDS_REVIEW", "FAILED", "NOT_RUN")
PUBLICATION = ("published", "staged")
READINESS = ("VERIFIED", "NEEDS_REVIEW", "LICENSE_REQUIRED", "PROVENANCE_UNCLEAR", "UNAVAILABLE", "OWNER_UPLOAD_REQUIRED")
TARGET_KINDS = ("hadith_collection", "hadith_translation_edition", "quran_translation_edition", "quran_translation_editions", "tafsir_editions", "tafsir_translation_edition")
REQUIRED_TEXT = ("id", "name", "purpose", "category", "entity_type", "provenance", "import_method", "remaining_action", "last_checked")


def manifest_path() -> Path:
    candidates = [os.environ.get("WOI_MANIFEST_PATH"), str(Path(__file__).resolve().parents[4] / "data" / "source-manifest.json"), "/app/data/source-manifest.json"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise FileNotFoundError("data/source-manifest.json not found (set WOI_MANIFEST_PATH)")


def load_manifest(path: Path | None = None) -> dict:
    return json.loads((path or manifest_path()).read_text(encoding="utf-8"))


def validate_manifest(manifest: dict) -> list[str]:
    """Every problem found, as human-readable strings. An empty list means the manifest is consistent."""
    problems: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(manifest.get("datasets", [])):
        ident = entry.get("id") or f"#{index}"
        where = f"dataset {ident}"
        if ident in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(ident)
        for key in REQUIRED_TEXT:
            if not str(entry.get(key) or "").strip():
                problems.append(f"{where}: missing {key}")
        source = entry.get("source") or {}
        if not str(source.get("name") or "").strip():
            problems.append(f"{where}: missing source.name")
        licence = entry.get("license") or {}
        if licence.get("status") not in LICENSE:
            problems.append(f"{where}: license.status must be one of {', '.join(LICENSE)}")
        if not str(licence.get("name") or "").strip():
            problems.append(f"{where}: missing license.name")
        if entry.get("validation_status") not in VALIDATION:
            problems.append(f"{where}: invalid validation_status")
        if entry.get("publication_status") not in PUBLICATION:
            problems.append(f"{where}: invalid publication_status")
        if entry.get("readiness") not in READINESS:
            problems.append(f"{where}: invalid readiness")
        if entry.get("date_acquired"):
            for key in ("importer", "importer_version"):
                if not str(entry.get(key) or "").strip():
                    problems.append(f"{where}: acquired data needs {key}")
            if not str(source.get("version") or "").strip():
                problems.append(f"{where}: acquired data needs source.version")
            if not str(source.get("url") or "").strip():
                problems.append(f"{where}: acquired data needs source.url")
        for target in entry.get("targets", []):
            if target.get("kind") not in TARGET_KINDS:
                problems.append(f"{where}: unknown target kind {target.get('kind')}")
        if entry.get("publication_status") == "published":
            allowed, reasons = can_publish(license_status=licence.get("status", "UNKNOWN"), validation_status=entry.get("validation_status", "NOT_RUN"),
                                           rights_confirmation=entry.get("rights_confirmation"))
            if not allowed:
                problems.append(f"{where}: published but not publishable ({'; '.join(reasons)})")
            if entry.get("readiness") not in ("VERIFIED", "NEEDS_REVIEW"):
                problems.append(f"{where}: published datasets must be VERIFIED or NEEDS_REVIEW, not {entry.get('readiness')}")
            if not entry.get("public"):
                problems.append(f"{where}: published datasets must set public=true")
        else:
            if entry.get("public"):
                problems.append(f"{where}: staged datasets must set public=false")
        if licence.get("status") not in PUBLISHABLE_LICENCE_STATUSES and entry.get("publication_status") == "published":
            problems.append(f"{where}: licence status {licence.get('status')} cannot be published")
        if entry.get("date_acquired") and entry.get("category") != "directory" and not (entry.get("checksum_sha256") or entry.get("integrity") or entry.get("targets") is not None):
            problems.append(f"{where}: acquired data needs a checksum or integrity statement")
    return problems
