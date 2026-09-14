from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class KnowledgeSyncPeerAttestation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_peer_attestations"
    __table_args__ = (
        CheckConstraint("status IN ('pending','active','expired','revoked')", name="ck_knowledge_sync_peer_attestation_status"),
        UniqueConstraint("node_id", "attestation_version", name="uq_knowledge_sync_peer_attestation_node_version"),
        Index("ix_knowledge_sync_peer_attestation_node_status", "node_id", "status"),
    )

    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False)
    node_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_nodes.id", ondelete="CASCADE"), nullable=False)
    attestation_version: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    independent_reviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_in_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")


class KnowledgeSyncPolicyChange(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_policy_changes"
    __table_args__ = (
        CheckConstraint("status IN ('proposed','approved','rejected','applied','rolled_back')", name="ck_knowledge_sync_policy_change_status"),
        CheckConstraint("risk_level IN ('low','medium','high','critical')", name="ck_knowledge_sync_policy_change_risk"),
        Index("ix_knowledge_sync_policy_change_policy_status", "trust_policy_id", "status"),
    )

    trust_policy_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_trust_policies.id", ondelete="CASCADE"), nullable=False)
    requested_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    change_ticket: Mapped[str] = mapped_column(String(120), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    before_policy_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    after_policy_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="proposed", server_default="proposed")


class KnowledgeSyncSecurityIncident(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_security_incidents"
    __table_args__ = (
        CheckConstraint("severity IN ('low','medium','high','critical')", name="ck_knowledge_sync_security_incident_severity"),
        CheckConstraint("status IN ('open','contained','resolved','dismissed')", name="ck_knowledge_sync_security_incident_status"),
        Index("ix_knowledge_sync_security_incident_node_status", "node_id", "status"),
    )

    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False)
    node_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_nodes.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[UUID | None] = mapped_column(ForeignKey("knowledge_sync_runs.id", ondelete="SET NULL"), nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open", server_default="open")
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    node_suspended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    credentials_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    transfers_cancelled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    summary: Mapped[str] = mapped_column(Text, nullable=False)


class KnowledgeSyncQuarantine(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_quarantines"
    __table_args__ = (
        CheckConstraint("status IN ('active','release_pending','released','expired')", name="ck_knowledge_sync_quarantine_status"),
        UniqueConstraint("incident_id", name="uq_knowledge_sync_quarantine_incident"),
    )

    incident_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_security_incidents.id", ondelete="CASCADE"), nullable=False)
    node_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sync_nodes.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    release_evidence_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    integrity_verification_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    credentials_rotated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    independent_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class KnowledgeSyncAcceptanceReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sync_acceptance_reviews"
    __table_args__ = (
        CheckConstraint("outcome IN ('pending','passed','failed','conditional')", name="ck_knowledge_sync_acceptance_review_outcome"),
        UniqueConstraint("organisation_id", "review_version", name="uq_knowledge_sync_acceptance_org_version"),
    )

    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False)
    review_version: Mapped[str] = mapped_column(String(40), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    open_high_incidents: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    open_critical_incidents: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    controls_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
