from __future__ import annotations
from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class ComplianceFramework(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "compliance_frameworks"
    __table_args__ = (
        CheckConstraint("status IN ('draft','active','retired')", name="ck_compliance_framework_status"),
        UniqueConstraint("code", "version", name="uq_compliance_framework_code_version"),
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    jurisdiction: Mapped[str | None] = mapped_column(String(80), nullable=True)

class ComplianceControl(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "compliance_controls"
    __table_args__ = (
        CheckConstraint("status IN ('planned','implemented','tested','failed','not_applicable')", name="ck_compliance_control_status"),
        UniqueConstraint("framework_id", "control_key", name="uq_compliance_control_framework_key"),
        Index("ix_compliance_control_framework_status", "framework_id", "status"),
    )
    framework_id: Mapped[UUID] = mapped_column(ForeignKey("compliance_frameworks.id", ondelete="CASCADE"), nullable=False)
    control_key: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="planned", server_default="planned")
    test_frequency_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365, server_default="365")

class ComplianceEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "compliance_evidence"
    __table_args__ = (
        CheckConstraint("classification IN ('public','internal','confidential','restricted')", name="ck_compliance_evidence_classification"),
        CheckConstraint("retention_days BETWEEN 1 AND 3650", name="ck_compliance_evidence_retention"),
        Index("ix_compliance_evidence_control_created", "control_id", "created_at"),
    )
    control_id: Mapped[UUID] = mapped_column(ForeignKey("compliance_controls.id", ondelete="CASCADE"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(80), nullable=False)
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False, default="internal", server_default="internal")
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365, server_default="365")
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

class EnterpriseRisk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "enterprise_risks"
    __table_args__ = (
        CheckConstraint("likelihood BETWEEN 1 AND 5", name="ck_enterprise_risk_likelihood"),
        CheckConstraint("impact BETWEEN 1 AND 5", name="ck_enterprise_risk_impact"),
        CheckConstraint("status IN ('open','mitigating','accepted','closed')", name="ck_enterprise_risk_status"),
        Index("ix_enterprise_risk_status", "status"),
    )
    risk_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    likelihood: Mapped[int] = mapped_column(Integer, nullable=False)
    impact: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open", server_default="open")
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    treatment_plan: Mapped[str | None] = mapped_column(Text, nullable=True)

class DisasterRecoveryPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "disaster_recovery_plans"
    __table_args__ = (
        CheckConstraint("status IN ('draft','approved','tested','failed','retired')", name="ck_disaster_recovery_plan_status"),
        CheckConstraint("rpo_minutes >= 0", name="ck_disaster_recovery_plan_rpo"),
        CheckConstraint("rto_minutes > 0", name="ck_disaster_recovery_plan_rto"),
        UniqueConstraint("environment_id", "name", name="uq_disaster_recovery_plan_environment_name"),
    )
    environment_id: Mapped[UUID] = mapped_column(ForeignKey("deployment_environments.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    rpo_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    rto_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    multi_region: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    encrypted_backups: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    last_test_evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
