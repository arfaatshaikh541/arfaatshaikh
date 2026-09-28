"""Candidate profile, facts and CV version management."""
from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..config import get_config
from ..models import (
    Application,
    CandidateFact,
    CandidateProfile,
    CVVersion,
    FactStatus,
    utcnow,
)
from ..security.vault import Vault, get_vault
from .cv_parser import CVParseError, detect_kind, extract_text, parse_cv_text
from .knowledge import KnowledgeBase
from .schema import Preferences, Rules

CV_MIME = {"pdf": "application/pdf",
           "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
           "txt": "text/plain"}


def get_or_create_profile(s: Session, user_id: int) -> CandidateProfile:
    p = s.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user_id))
    if p is None:
        p = CandidateProfile(user_id=user_id, preferences=Preferences().model_dump(), rules=Rules().model_dump())
        s.add(p)
        s.flush()
    return p


def preferences(p: CandidateProfile) -> Preferences:
    return Preferences.model_validate(p.preferences or {})


def rules(p: CandidateProfile) -> Rules:
    return Rules.model_validate(p.rules or {})


def knowledge(s: Session, p: CandidateProfile) -> KnowledgeBase:
    facts = s.scalars(select(CandidateFact).where(CandidateFact.profile_id == p.id)).all()
    return KnowledgeBase(facts, allow_inferred=rules(p).allow_inferred_answers)


def set_fact(
    s: Session,
    p: CandidateProfile,
    category: str,
    key: str,
    value: str | None,
    *,
    group_key: str | None = None,
    status: FactStatus = FactStatus.VERIFIED,
    source: str = "USER",
    source_ref: str | None = None,
    excerpt: str | None = None,
    replace: bool = True,
) -> CandidateFact:
    """Create or update a fact. Candidate-entered facts are VERIFIED with source USER."""
    f = None
    if replace:
        f = s.scalar(
            select(CandidateFact).where(
                CandidateFact.profile_id == p.id,
                CandidateFact.category == category,
                CandidateFact.key == key,
                CandidateFact.group_key.is_(None) if group_key is None else CandidateFact.group_key == group_key,
            )
        )
    if f is None:
        f = CandidateFact(profile_id=p.id, category=category, key=key, group_key=group_key)
        s.add(f)
    f.value = value
    f.status = status.value
    f.source = source
    f.source_ref = source_ref
    f.source_excerpt = excerpt
    f.updated_at = utcnow()
    f.verified_at = utcnow() if status == FactStatus.VERIFIED else None
    s.flush()
    return f


def verify_fact(s: Session, p: CandidateProfile, fact_id: int, value: str | None = None) -> CandidateFact:
    f = s.get(CandidateFact, fact_id)
    if f is None or f.profile_id != p.id:
        raise LookupError("fact not found")
    if value is not None and value != f.value:
        f.value = value
        f.source = "USER"  # corrected by the candidate
    f.status = FactStatus.VERIFIED.value
    f.verified_at = f.updated_at = utcnow()
    return f


def new_group_key(prefix: str) -> str:
    return f"{prefix}:{secrets.token_hex(4)}"


# ------------------------------------------------------------------------- CVs


def _cv_path(profile_id: int, sha: str) -> Path:
    d = get_config().files_dir / f"profile-{profile_id}"
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    return d / f"cv-{sha}.bin"


def store_cv(
    s: Session, p: CandidateProfile, filename: str, data: bytes, vault: Vault | None = None, activate: bool = True
) -> CVVersion:
    cfg = get_config()
    if len(data) > cfg.max_upload_mb * 1024 * 1024:
        raise CVParseError(f"CV larger than {cfg.max_upload_mb} MB")
    kind = detect_kind(filename, data)
    vault = vault or get_vault()
    sha = hashlib.sha256(data).hexdigest()
    safe_name = os.path.basename(filename).replace("\x00", "")[:200] or f"cv.{kind}"
    version = (s.scalar(select(func.max(CVVersion.version)).where(CVVersion.profile_id == p.id)) or 0) + 1
    path = _cv_path(p.id, sha)
    path.write_bytes(vault.encrypt(data, f"cv:{p.id}:{sha}".encode()))
    os.chmod(path, 0o600)
    cv = CVVersion(
        profile_id=p.id, version=version, filename=safe_name, mime_type=CV_MIME[kind],
        size_bytes=len(data), sha256=sha, storage_path=str(path),
    )
    s.add(cv)
    s.flush()
    try:
        text = extract_text(safe_name, data)
        parsed = parse_cv_text(text)
        cv.parse_status = "PARSED"
        cv.extracted_text_chars = len(text)
        for ef in parsed.facts:
            s.add(CandidateFact(
                profile_id=p.id, category=ef.category, key=ef.key[:128], value=ef.value,
                group_key=(f"{ef.group_key}v{version}" if ef.group_key else None),
                status=FactStatus.EXTRACTED.value, source="CV", source_ref=f"cv_version:{cv.id}",
                source_excerpt=ef.excerpt[:2000],
            ))
    except CVParseError as e:
        cv.parse_status = "FAILED"
        cv.parse_error = str(e)
    if activate:
        activate_cv(s, p, cv)
    s.flush()
    return cv


def activate_cv(s: Session, p: CandidateProfile, cv: CVVersion) -> None:
    for other in s.scalars(select(CVVersion).where(CVVersion.profile_id == p.id)):
        other.is_active = other.id == cv.id
    s.flush()


def read_cv(cv: CVVersion, vault: Vault | None = None) -> bytes:
    vault = vault or get_vault()
    data = vault.decrypt(Path(cv.storage_path).read_bytes(), f"cv:{cv.profile_id}:{cv.sha256}".encode())
    if hashlib.sha256(data).hexdigest() != cv.sha256:
        raise ValueError("CV integrity check failed")
    return data


def active_cv(s: Session, p: CandidateProfile) -> CVVersion | None:
    return s.scalar(select(CVVersion).where(CVVersion.profile_id == p.id, CVVersion.is_active.is_(True)))


def cv_usage(s: Session, cv_id: int) -> int:
    return s.scalar(select(func.count(Application.id)).where(Application.cv_version_id == cv_id)) or 0


# ------------------------------------------------------------------------- privacy


def export_profile(s: Session, p: CandidateProfile) -> dict[str, Any]:
    facts = s.scalars(select(CandidateFact).where(CandidateFact.profile_id == p.id)).all()
    cvs = s.scalars(select(CVVersion).where(CVVersion.profile_id == p.id)).all()
    return {
        "exported_at": utcnow().isoformat(),
        "preferences": p.preferences,
        "rules": p.rules,
        "facts": [
            {"id": f.id, "category": f.category, "key": f.key, "value": f.value, "group": f.group_key,
             "status": f.status, "source": f.source, "source_ref": f.source_ref}
            for f in facts
        ],
        "cv_versions": [
            {"version": c.version, "filename": c.filename, "sha256": c.sha256, "uploaded_at": c.uploaded_at.isoformat(),
             "active": c.is_active}
            for c in cvs
        ],
    }


def delete_candidate_data(s: Session, p: CandidateProfile) -> None:
    """Delete facts, CV files and CV records. Application history keeps job/audit data."""
    for cv in s.scalars(select(CVVersion).where(CVVersion.profile_id == p.id)):
        try:
            Path(cv.storage_path).unlink(missing_ok=True)
        except OSError:
            pass
    s.execute(delete(CandidateFact).where(CandidateFact.profile_id == p.id))
    s.execute(CVVersion.__table__.delete().where(CVVersion.profile_id == p.id))
    p.preferences = Preferences().model_dump()
    p.rules = Rules().model_dump()
    p.onboarding_complete = False
