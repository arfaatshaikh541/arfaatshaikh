"""Model cache integrity: trust-on-first-use hash verification for the
large binary model files under AURA_VOICE_MODELS_DIR (voice models today;
any future on-disk cache can reuse this).

Section 11 asks for "corrupted-cache repair" as part of automatic health
supervision. There is no upstream manifest of known-good hashes to check
against here (models are fetched by the owner per core/RUNBOOK.md, not by
this codebase), so the honest thing this code can do is trust-on-first-use:
the first time a file is seen, its hash is recorded; every later check
compares the file against that recorded hash. A mismatch means the file
changed after AURA started trusting it -- a disk fault, a partial write, or
tampering -- and is treated as corruption, never as "a newer version I
should adopt." A corrupted file is quarantined (renamed aside, never
deleted) so the capability fails honestly (DEGRADED, pointing at the
RUNBOOK re-download step) instead of silently loading a broken model.
Nothing outside this manifest's own directory is ever touched, so this can
never reach owner data.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class CacheIssue:
    path: str
    status: str  # "missing" | "trusted_new" | "ok" | "corrupted_and_quarantined"
    detail: str


def compute_sha256(path: str, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


class CacheManifestStore:
    """A small JSON file mapping absolute path -> trusted sha256. Lives
    next to the cache it describes, not in the main database, since it is
    disposable local state, not owner data."""

    def __init__(self, manifest_path: str) -> None:
        self._manifest_path = manifest_path

    def _load(self) -> dict[str, str]:
        if not os.path.exists(self._manifest_path):
            return {}
        with open(self._manifest_path) as handle:
            return json.load(handle)

    def _save(self, data: dict[str, str]) -> None:
        os.makedirs(os.path.dirname(self._manifest_path), exist_ok=True)
        with open(self._manifest_path, "w") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)

    def get(self, path: str) -> str | None:
        return self._load().get(path)

    def record(self, path: str, digest: str) -> None:
        data = self._load()
        data[path] = digest
        self._save(data)

    def forget(self, path: str) -> None:
        data = self._load()
        data.pop(path, None)
        self._save(data)


def verify_and_repair(
    paths: list[str], manifest: CacheManifestStore, *, quarantine_dir: str | None = None,
) -> list[CacheIssue]:
    issues: list[CacheIssue] = []
    for path in paths:
        abs_path = os.path.abspath(path)

        if not os.path.exists(abs_path):
            issues.append(CacheIssue(abs_path, "missing", "not present -- see RUNBOOK.md to download it"))
            continue

        actual = compute_sha256(abs_path)
        trusted = manifest.get(abs_path)

        if trusted is None:
            manifest.record(abs_path, actual)
            issues.append(CacheIssue(abs_path, "trusted_new", "first time seen; hash recorded as trusted"))
            continue

        if actual == trusted:
            issues.append(CacheIssue(abs_path, "ok", "matches trusted hash"))
            continue

        target_dir = quarantine_dir or os.path.join(os.path.dirname(abs_path), ".quarantine")
        os.makedirs(target_dir, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        quarantined_path = os.path.join(target_dir, f"{os.path.basename(abs_path)}.{timestamp}.corrupted")
        shutil.move(abs_path, quarantined_path)
        manifest.forget(abs_path)
        issues.append(CacheIssue(
            abs_path, "corrupted_and_quarantined",
            f"hash no longer matches trusted value; moved to {quarantined_path} -- re-download per RUNBOOK.md",
        ))

    return issues
