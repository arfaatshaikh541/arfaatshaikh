"""Evidence records. Every record is tied to a real application event."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from sqlalchemy.orm import Session

from .config import get_config
from .models import Application, ApplicationEvent, ApplicationEvidence
from .security.redact import redact
from .security.vault import get_vault

# Kinds that prove a submission happened. Anything else is supporting material.
SUBMISSION_PROOF_KINDS = {"CONFIRMATION_URL", "CONFIRMATION_TEXT", "APPLICATION_ID", "PLATFORM_RESPONSE",
                          "CONFIRMATION_EMAIL", "MANUAL_CONFIRMATION"}
OTHER_KINDS = {"SCREENSHOT", "PRE_SUBMIT_SCREENSHOT", "CHALLENGE_SCREENSHOT", "ERROR_SCREENSHOT"}


def add_evidence(s: Session, app: Application, event: ApplicationEvent, kind: str, *, value: str | None = None,
                 url: str | None = None, png: bytes | None = None) -> ApplicationEvidence:
    if kind not in SUBMISSION_PROOF_KINDS | OTHER_KINDS:
        raise ValueError(f"Unknown evidence kind {kind}")
    if event.application_id != app.id:
        raise ValueError("Evidence must be tied to an event of the same application")
    path = sha = None
    if png is not None:
        sha = hashlib.sha256(png).hexdigest()
        d = get_config().evidence_dir / f"app-{app.id}"
        d.mkdir(parents=True, exist_ok=True, mode=0o700)
        p = d / f"{kind.lower()}-{event.id}-{sha[:12]}.png.enc"
        p.write_bytes(get_vault().encrypt(png, f"evidence:{app.id}:{sha}".encode()))
        os.chmod(p, 0o600)
        path = str(p)
    ev = ApplicationEvidence(application_id=app.id, event_id=event.id, kind=kind,
                             value=redact(value) if value else None, url=url, file_path=path, sha256=sha)
    s.add(ev)
    s.flush()
    return ev


def read_evidence_png(ev: ApplicationEvidence) -> bytes:
    if not ev.file_path:
        raise FileNotFoundError("Evidence has no file")
    data = get_vault().decrypt(Path(ev.file_path).read_bytes(), f"evidence:{ev.application_id}:{ev.sha256}".encode())
    if hashlib.sha256(data).hexdigest() != ev.sha256:
        raise ValueError("Evidence integrity check failed")
    return data
