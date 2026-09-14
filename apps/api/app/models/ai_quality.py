from __future__ import annotations
from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class AIEvaluationDataset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_evaluation_datasets"
    __table_args__ = (
        CheckConstraint("status IN ('draft','approved','retired')", name="ck_ai_eval_dataset_status"),
        UniqueConstraint("dataset_key", "version", name="uq_ai_eval_dataset_key_version"),
    )
    dataset_key: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    evidence_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    contains_private_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

class AIEvaluationCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_evaluation_cases"
    __table_args__ = (
        CheckConstraint("risk_level IN ('low','medium','high','critical')", name="ck_ai_eval_case_risk"),
        CheckConstraint("expected_action IN ('answer','refuse','escalate')", name="ck_ai_eval_case_action"),
        Index("ix_ai_eval_case_dataset_risk", "dataset_id", "risk_level"),
    )
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("ai_evaluation_datasets.id", ondelete="CASCADE"), nullable=False)
    case_key: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    expected_action: Mapped[str] = mapped_column(String(16), nullable=False)
    required_source_passage_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    forbidden_claim_patterns: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")

class AIEvaluationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_evaluation_runs"
    __table_args__ = (
        CheckConstraint("status IN ('queued','running','passed','failed','blocked')", name="ck_ai_eval_run_status"),
        CheckConstraint("pass_rate >= 0 AND pass_rate <= 100", name="ck_ai_eval_run_pass_rate"),
        Index("ix_ai_eval_run_dataset_created", "dataset_id", "created_at"),
    )
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("ai_evaluation_datasets.id", ondelete="RESTRICT"), nullable=False)
    model_identifier: Mapped[str] = mapped_column(String(160), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", server_default="queued")
    pass_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")

class AIEvaluationResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_evaluation_results"
    __table_args__ = (
        CheckConstraint("observed_action IN ('answer','refuse','escalate','error')", name="ck_ai_eval_result_action"),
        CheckConstraint("score >= 0 AND score <= 100", name="ck_ai_eval_result_score"),
        UniqueConstraint("run_id", "case_id", name="uq_ai_eval_result_run_case"),
    )
    run_id: Mapped[UUID] = mapped_column(ForeignKey("ai_evaluation_runs.id", ondelete="CASCADE"), nullable=False)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("ai_evaluation_cases.id", ondelete="CASCADE"), nullable=False)
    observed_action: Mapped[str] = mapped_column(String(16), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    evidence_fingerprints: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    response_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

class AIRedTeamFinding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_red_team_findings"
    __table_args__ = (
        CheckConstraint("severity IN ('low','medium','high','critical')", name="ck_ai_red_team_severity"),
        CheckConstraint("status IN ('open','mitigated','accepted','false_positive')", name="ck_ai_red_team_status"),
        Index("ix_ai_red_team_status_severity", "status", "severity"),
    )
    evaluation_result_id: Mapped[UUID | None] = mapped_column(ForeignKey("ai_evaluation_results.id", ondelete="SET NULL"), nullable=True)
    attack_class: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", server_default="open")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    mitigation: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocks_release: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
