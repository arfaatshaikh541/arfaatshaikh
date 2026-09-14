from __future__ import annotations
from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class ProductionLaunchApproval(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "production_launch_approvals"
    __table_args__ = (
        CheckConstraint("status IN ('draft','review','approved','rejected','revoked')", name="ck_launch_approval_status"),
        CheckConstraint("approval_type IN ('security','privacy','scholarly','operations','product','executive')", name="ck_launch_approval_type"),
        UniqueConstraint("release_id", "approval_type", name="uq_launch_approval_release_type"),
        Index("ix_launch_approval_release_status", "release_id", "status"),
    )
    release_id: Mapped[UUID] = mapped_column(ForeignKey("deployment_releases.id", ondelete="CASCADE"), nullable=False)
    approval_type: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    approver_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

class TenantLifecycleExercise(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenant_lifecycle_exercises"
    __table_args__ = (
        CheckConstraint("exercise_type IN ('export','deletion','suspension','reactivation','archive','restore')", name="ck_tenant_lifecycle_exercise_type"),
        CheckConstraint("status IN ('planned','running','passed','failed','cancelled')", name="ck_tenant_lifecycle_exercise_status"),
        Index("ix_tenant_lifecycle_exercise_tenant_status", "organisation_id", "status"),
    )
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False)
    exercise_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="planned", server_default="planned")
    requested_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    evidence_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cross_tenant_access_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    records_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    result_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")

class FinalSecurityAudit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "final_security_audits"
    __table_args__ = (
        CheckConstraint("status IN ('planned','running','passed','failed','accepted_with_risk')", name="ck_final_security_audit_status"),
        CheckConstraint("critical_findings >= 0 AND high_findings >= 0 AND medium_findings >= 0 AND low_findings >= 0", name="ck_final_security_audit_counts"),
        Index("ix_final_security_audit_release_status", "release_id", "status"),
    )
    release_id: Mapped[UUID] = mapped_column(ForeignKey("deployment_releases.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="planned", server_default="planned")
    independent_auditor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    tenant_isolation_tested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    authorization_tested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    evidence_integrity_tested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    critical_findings: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    high_findings: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    medium_findings: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    low_findings: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    report_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

class MilestoneAcceptance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "milestone_acceptances"
    __table_args__ = (
        CheckConstraint("status IN ('draft','blocked','accepted','revoked')", name="ck_milestone_acceptance_status"),
        UniqueConstraint("milestone_key", "release_id", name="uq_milestone_acceptance_release"),
    )
    milestone_key: Mapped[str] = mapped_column(String(40), nullable=False)
    release_id: Mapped[UUID] = mapped_column(ForeignKey("deployment_releases.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    accepted_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verification_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    limitations: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
