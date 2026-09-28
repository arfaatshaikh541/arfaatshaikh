"""Database schema. PostgreSQL is the target; every table here is real state.

No seed/sample rows are ever inserted except the static platform registry,
which describes connectors (not jobs, not applications).
"""
from __future__ import annotations

import datetime as dt
import enum
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONType, list[Any]: JSONType}


def _ts(nullable: bool = False, default: bool = True):
    return mapped_column(
        DateTime(timezone=True), nullable=nullable, default=utcnow if default else None
    )


# --------------------------------------------------------------------------- enums


class FactStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"          # confirmed by the candidate
    EXTRACTED = "EXTRACTED"        # parsed from CV, awaiting candidate confirmation
    INFERRED = "INFERRED"          # derived; never used as a factual YES
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    CONFLICT = "CONFLICT"


class ApplicationStatus(str, enum.Enum):
    DISCOVERED = "DISCOVERED"
    EVALUATED = "EVALUATED"
    QUEUED = "QUEUED"
    STARTED = "STARTED"
    FORM_COMPLETED = "FORM_COMPLETED"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    VERIFIED = "VERIFIED"
    DRY_RUN_COMPLETE = "DRY_RUN_COMPLETE"
    SKIPPED = "SKIPPED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class Mode(str, enum.Enum):
    LIVE = "LIVE"
    DRY_RUN = "DRY_RUN"


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"   # exhausted retries
    CANCELLED = "CANCELLED"


class PlatformStatus(str, enum.Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    CONNECTED = "CONNECTED"
    LOGIN_FAILED = "LOGIN_FAILED"
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"
    NOT_AUTOMATABLE = "NOT_AUTOMATABLE"
    NO_LOGIN_REQUIRED = "NO_LOGIN_REQUIRED"


# --------------------------------------------------------------------------- auth


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = _ts()
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[dt.datetime | None] = _ts(nullable=True, default=False)


class WebSession(Base):
    __tablename__ = "web_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = _ts()
    expires_at: Mapped[dt.datetime] = _ts(default=False)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))


# --------------------------------------------------------------------------- candidate


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    preferences: Mapped[dict[str, Any]] = mapped_column(default=dict)
    rules: Mapped[dict[str, Any]] = mapped_column(default=dict)
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = _ts()
    updated_at: Mapped[dt.datetime] = _ts()

    facts: Mapped[list["CandidateFact"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class CandidateFact(Base):
    """A single candidate fact with provenance.

    ``group_key`` ties related facts together (one employment entry, one degree).
    """

    __tablename__ = "candidate_facts"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(64))
    key: Mapped[str] = mapped_column(String(128))
    value: Mapped[str | None] = mapped_column(Text)
    group_key: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default=FactStatus.UNKNOWN.value)
    source: Mapped[str] = mapped_column(String(64))  # USER | CV | PREVIOUS_ANSWER
    source_ref: Mapped[str | None] = mapped_column(String(128))  # e.g. cv_version id
    source_excerpt: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = _ts()
    updated_at: Mapped[dt.datetime] = _ts()
    verified_at: Mapped[dt.datetime | None] = _ts(nullable=True, default=False)

    profile: Mapped[CandidateProfile] = relationship(back_populates="facts")

    __table_args__ = (Index("ix_facts_profile_cat_key", "profile_id", "category", "key"),)


class CVVersion(Base):
    __tablename__ = "cv_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str] = mapped_column(String(1024))  # encrypted blob, outside web root
    source: Mapped[str] = mapped_column(String(64), default="upload")
    uploaded_at: Mapped[dt.datetime] = _ts()
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    parse_status: Mapped[str] = mapped_column(String(32), default="PENDING")
    parse_error: Mapped[str | None] = mapped_column(Text)
    extracted_text_chars: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (UniqueConstraint("profile_id", "version"),)


# --------------------------------------------------------------------------- secrets


class Credential(Base):
    __tablename__ = "credentials"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    platform_key: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(128), default="default")
    username: Mapped[str | None] = mapped_column(String(320))
    blob: Mapped[bytes] = mapped_column(LargeBinary)  # vault envelope (see vault.py)
    key_id: Mapped[str] = mapped_column(String(32))
    mfa_mode: Mapped[str] = mapped_column(String(32), default="none")  # none|manual
    rotate_after_days: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = _ts()
    updated_at: Mapped[dt.datetime] = _ts()
    last_used_at: Mapped[dt.datetime | None] = _ts(nullable=True, default=False)

    __table_args__ = (UniqueConstraint("user_id", "platform_key", "label"),)


class Platform(Base):
    __tablename__ = "platforms"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    automatable: Mapped[bool] = mapped_column(Boolean)
    requires_login: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String(32), default=PlatformStatus.NOT_CONFIGURED.value)
    status_reason: Mapped[str | None] = mapped_column(Text)
    last_tested_at: Mapped[dt.datetime | None] = _ts(nullable=True, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict[str, Any]] = mapped_column(default=dict)  # non-secret (login URL, selectors)


class PlatformSession(Base):
    __tablename__ = "platform_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    platform_key: Mapped[str] = mapped_column(ForeignKey("platforms.key", ondelete="CASCADE"))
    credential_id: Mapped[int | None] = mapped_column(ForeignKey("credentials.id", ondelete="SET NULL"))
    storage_state_blob: Mapped[bytes] = mapped_column(LargeBinary)  # encrypted cookies
    key_id: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[dt.datetime] = _ts()
    last_validated_at: Mapped[dt.datetime | None] = _ts(nullable=True, default=False)
    valid: Mapped[bool] = mapped_column(Boolean, default=True)


# --------------------------------------------------------------------------- jobs


class JobSource(Base):
    __tablename__ = "job_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    connector: Mapped[str] = mapped_column(String(32))  # greenhouse|lever|ashby
    identifier: Mapped[str] = mapped_column(String(255))  # board token / company slug
    display_name: Mapped[str | None] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    options: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[dt.datetime] = _ts()
    last_run_at: Mapped[dt.datetime | None] = _ts(nullable=True, default=False)
    last_success_at: Mapped[dt.datetime | None] = _ts(nullable=True, default=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    last_job_count: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (UniqueConstraint("connector", "identifier"),)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("job_sources.id", ondelete="SET NULL"))
    platform: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(255))
    board: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(2048))
    canonical_url: Mapped[str] = mapped_column(String(2048))
    apply_url: Mapped[str | None] = mapped_column(String(2048))
    apply_method: Mapped[str] = mapped_column(String(64))  # e.g. greenhouse_hosted_form
    company: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(512))
    location: Mapped[str | None] = mapped_column(String(512))
    workplace_type: Mapped[str | None] = mapped_column(String(32))  # remote|hybrid|onsite|None=UNKNOWN
    employment_type: Mapped[str | None] = mapped_column(String(64))
    salary_min: Mapped[float | None] = mapped_column(Float)
    salary_max: Mapped[float | None] = mapped_column(Float)
    salary_currency: Mapped[str | None] = mapped_column(String(8))
    salary_interval: Mapped[str | None] = mapped_column(String(32))
    salary_text: Mapped[str | None] = mapped_column(Text)
    experience_years_min: Mapped[float | None] = mapped_column(Float)
    experience_text: Mapped[str | None] = mapped_column(Text)
    skills: Mapped[list[Any]] = mapped_column(default=list)
    description_text: Mapped[str | None] = mapped_column(Text)
    description_hash: Mapped[str | None] = mapped_column(String(64))
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    published_at: Mapped[dt.datetime | None] = _ts(nullable=True, default=False)
    discovered_at: Mapped[dt.datetime] = _ts()
    last_seen_at: Mapped[dt.datetime] = _ts()
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(32), default="DISCOVERED")
    raw: Mapped[dict[str, Any]] = mapped_column(default=dict)

    match: Mapped["JobMatch | None"] = relationship(back_populates="job", uselist=False)

    __table_args__ = (UniqueConstraint("platform", "board", "external_id"),)


class JobMatch(Base):
    __tablename__ = "job_matches"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), unique=True)
    score: Mapped[float] = mapped_column(Float)
    criteria: Mapped[list[Any]] = mapped_column(default=list)
    decision: Mapped[str] = mapped_column(String(32))  # APPLY|SKIP|REVIEW
    decision_reasons: Mapped[list[Any]] = mapped_column(default=list)
    rules_snapshot: Mapped[dict[str, Any]] = mapped_column(default=dict)
    evaluated_at: Mapped[dt.datetime] = _ts()

    job: Mapped[Job] = relationship(back_populates="match")


# --------------------------------------------------------------------------- applications


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32), default=ApplicationStatus.EVALUATED.value)
    cv_version_id: Mapped[int | None] = mapped_column(ForeignKey("cv_versions.id", ondelete="SET NULL"))
    created_at: Mapped[dt.datetime] = _ts()
    queued_at: Mapped[dt.datetime | None] = _ts(nullable=True, default=False)
    started_at: Mapped[dt.datetime | None] = _ts(nullable=True, default=False)
    submitted_at: Mapped[dt.datetime | None] = _ts(nullable=True, default=False)
    finished_at: Mapped[dt.datetime | None] = _ts(nullable=True, default=False)
    updated_at: Mapped[dt.datetime] = _ts()
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    external_application_id: Mapped[str | None] = mapped_column(String(255))
    browser_session_id: Mapped[str | None] = mapped_column(String(64))
    worker_id: Mapped[str | None] = mapped_column(String(128))
    last_error: Mapped[str | None] = mapped_column(Text)
    status_reason: Mapped[str | None] = mapped_column(Text)

    job: Mapped[Job] = relationship()
    events: Mapped[list["ApplicationEvent"]] = relationship(
        back_populates="application", order_by="ApplicationEvent.id", cascade="all, delete-orphan"
    )
    evidence: Mapped[list["ApplicationEvidence"]] = relationship(
        back_populates="application", order_by="ApplicationEvidence.id", cascade="all, delete-orphan"
    )
    questions: Mapped[list["ApplicationQuestion"]] = relationship(
        back_populates="application", order_by="ApplicationQuestion.id", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("job_id", "mode"), Index("ix_app_status", "status"))


class ApplicationQuestion(Base):
    __tablename__ = "application_questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(Text)
    field_name: Mapped[str | None] = mapped_column(String(512))
    field_type: Mapped[str] = mapped_column(String(32))
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    options: Mapped[list[Any]] = mapped_column(default=list)
    intent: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = _ts()

    application: Mapped[Application] = relationship(back_populates="questions")
    answer: Mapped["ApplicationAnswer | None"] = relationship(
        back_populates="question", uselist=False, cascade="all, delete-orphan"
    )


class ApplicationAnswer(Base):
    __tablename__ = "application_answers"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("application_questions.id", ondelete="CASCADE"), unique=True
    )
    answer_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))  # ANSWERED|UNKNOWN|REJECTED
    confidence: Mapped[str] = mapped_column(String(16))  # high|medium|low|none
    provenance: Mapped[dict[str, Any]] = mapped_column(default=dict)
    fabricated_information_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    filled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = _ts()

    question: Mapped[ApplicationQuestion] = relationship(back_populates="answer")


class ApplicationEvent(Base):
    __tablename__ = "application_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    ts: Mapped[dt.datetime] = _ts()
    event: Mapped[str] = mapped_column(String(64))
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str | None] = mapped_column(String(32))
    worker_id: Mapped[str | None] = mapped_column(String(128))
    url: Mapped[str | None] = mapped_column(String(2048))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict[str, Any]] = mapped_column(default=dict)

    application: Mapped[Application] = relationship(back_populates="events")


class ApplicationEvidence(Base):
    __tablename__ = "application_evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    event_id: Mapped[int] = mapped_column(ForeignKey("application_events.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32))
    value: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(2048))
    file_path: Mapped[str | None] = mapped_column(String(1024))
    sha256: Mapped[str | None] = mapped_column(String(64))
    captured_at: Mapped[dt.datetime] = _ts()

    application: Mapped[Application] = relationship(back_populates="evidence")


# --------------------------------------------------------------------------- ops


class ErrorRecord(Base):
    __tablename__ = "errors"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[dt.datetime] = _ts()
    component: Mapped[str] = mapped_column(String(64))
    worker_id: Mapped[str | None] = mapped_column(String(128))
    platform: Mapped[str | None] = mapped_column(String(64))
    job_id: Mapped[int | None] = mapped_column(Integer)
    application_id: Mapped[int | None] = mapped_column(Integer)
    task_id: Mapped[int | None] = mapped_column(Integer)
    error_type: Mapped[str] = mapped_column(String(128))
    message: Mapped[str] = mapped_column(Text)
    traceback: Mapped[str | None] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_date: Mapped[dt.date] = mapped_column(index=True)
    timezone: Mapped[str] = mapped_column(String(64))
    generated_at: Mapped[dt.datetime] = _ts()
    trigger: Mapped[str] = mapped_column(String(32))  # scheduled|manual
    data: Mapped[dict[str, Any]] = mapped_column(default=dict)
    text: Mapped[str] = mapped_column(Text)


class SystemEvent(Base):
    __tablename__ = "system_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[dt.datetime] = _ts()
    component: Mapped[str] = mapped_column(String(64))
    event: Mapped[str] = mapped_column(String(64))
    worker_id: Mapped[str | None] = mapped_column(String(128))
    detail: Mapped[dict[str, Any]] = mapped_column(default=dict)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[dt.datetime] = _ts()
    actor: Mapped[str] = mapped_column(String(320))
    action: Mapped[str] = mapped_column(String(128))
    target: Mapped[str | None] = mapped_column(String(255))
    ip: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict[str, Any]] = mapped_column(default=dict)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
    status: Mapped[str] = mapped_column(String(16), default=TaskStatus.PENDING.value)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    run_after: Mapped[dt.datetime] = _ts()
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    locked_by: Mapped[str | None] = mapped_column(String(128))
    locked_until: Mapped[dt.datetime | None] = _ts(nullable=True, default=False)
    dedupe_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    created_at: Mapped[dt.datetime] = _ts()
    finished_at: Mapped[dt.datetime | None] = _ts(nullable=True, default=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any]] = mapped_column(default=dict)

    __table_args__ = (Index("ix_tasks_claim", "status", "run_after", "priority"),)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    worker_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))  # scheduler|worker
    started_at: Mapped[dt.datetime] = _ts()
    last_seen: Mapped[dt.datetime] = _ts()
    current_task_id: Mapped[int | None] = mapped_column(Integer)
    info: Mapped[dict[str, Any]] = mapped_column(default=dict)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(default=dict)
    updated_at: Mapped[dt.datetime] = _ts()


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    next_allowed_at: Mapped[dt.datetime] = _ts()
    backoff_seconds: Mapped[float] = mapped_column(Float, default=0.0)
