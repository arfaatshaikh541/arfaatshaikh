from __future__ import annotations

import re
import uuid
from pathlib import Path

from core.config import settings

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(filename: str) -> str:
    name = Path(filename).name  # strip any directory components — no path traversal via filename
    name = _UNSAFE_CHARS.sub("_", name).strip("._")
    return name[:200] or "file"


def _root() -> Path:
    root = Path(settings.evidence_storage_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve(stored_path: str) -> Path:
    root = _root()
    resolved = (root / stored_path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("Invalid stored evidence path.")
    return resolved


def save_evidence_file(*, tenant_id: uuid.UUID, evidence_id: uuid.UUID, filename: str, content: bytes) -> str:
    """Writes `content` to a real file on local disk, scoped under a
    per-tenant subdirectory of `settings.evidence_storage_root`. Returns
    the stored path (relative to the storage root) to persist on the
    `EvidenceRecord` row.

    Not S3/MinIO-compatible object storage — the dormant `object_storage_*`
    settings still describe that (unreachable here: a real MinIO instance
    needs a Docker daemon this sandboxed environment doesn't have). This is
    a genuinely real, but intentionally scoped-down, local-disk store —
    same tradeoff Milestone 27 made for DNS-TXT verification with a local
    test server standing in for a live public DNS path."""
    tenant_dir = _root() / str(tenant_id)
    tenant_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{evidence_id}__{_safe_filename(filename)}"
    (tenant_dir / stored_name).write_bytes(content)
    return f"{tenant_id}/{stored_name}"


def read_evidence_file(stored_path: str) -> bytes:
    return _resolve(stored_path).read_bytes()


def delete_evidence_file(stored_path: str) -> None:
    _resolve(stored_path).unlink(missing_ok=True)
