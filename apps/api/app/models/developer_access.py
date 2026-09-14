from __future__ import annotations

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class APIAccessDecision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_access_decisions"
    __table_args__ = (
        CheckConstraint("decision IN ('allow','deny')", name="ck_api_access_decision_result"),
        CheckConstraint("response_status_code >= 100 AND response_status_code <= 599", name="ck_api_access_decision_status_code"),
        Index("ix_api_access_decision_credential_created", "credential_id", "created_at"),
        Index("ix_api_access_decision_org_created", "organisation_id", "created_at"),
    )

    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("developer_applications.id", ondelete="CASCADE"), nullable=False)
    credential_id: Mapped[UUID] = mapped_column(ForeignKey("api_client_credentials.id", ondelete="CASCADE"), nullable=False)
    request_id: Mapped[str] = mapped_column(String(80), nullable=False)
    route_template: Mapped[str] = mapped_column(String(180), nullable=False)
    required_scope: Mapped[str] = mapped_column(String(80), nullable=False)
    decision: Mapped[str] = mapped_column(String(8), nullable=False)
    response_status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    client_ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class APIUsageRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_usage_records"
    __table_args__ = (
        CheckConstraint("billable_units >= 0", name="ck_api_usage_record_units"),
        CheckConstraint("response_status_code >= 100 AND response_status_code <= 599", name="ck_api_usage_record_status_code"),
        UniqueConstraint("credential_id", "idempotency_key", name="uq_api_usage_record_credential_idempotency"),
        Index("ix_api_usage_record_credential_created", "credential_id", "created_at"),
    )

    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("developer_applications.id", ondelete="CASCADE"), nullable=False)
    credential_id: Mapped[UUID] = mapped_column(ForeignKey("api_client_credentials.id", ondelete="CASCADE"), nullable=False)
    request_id: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    route_template: Mapped[str] = mapped_column(String(180), nullable=False)
    response_status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    billable_units: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    usage_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")


class APIQuotaWindow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_quota_windows"
    __table_args__ = (
        CheckConstraint("request_count >= 0", name="ck_api_quota_window_count"),
        CheckConstraint("limit_count > 0", name="ck_api_quota_window_limit"),
        UniqueConstraint("credential_id", "window_key", name="uq_api_quota_window_credential_window"),
        Index("ix_api_quota_window_credential", "credential_id"),
    )

    credential_id: Mapped[UUID] = mapped_column(ForeignKey("api_client_credentials.id", ondelete="CASCADE"), nullable=False)
    window_key: Mapped[str] = mapped_column(String(80), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    limit_count: Mapped[int] = mapped_column(Integer, nullable=False)
    resets_at_iso: Mapped[str] = mapped_column(String(40), nullable=False)


class DeveloperAuditEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "developer_audit_events"
    __table_args__ = (
        CheckConstraint("event_type IN ('credential.used','credential.denied','quota.exceeded','credential.rotated','credential.revoked','scope.changed')", name="ck_developer_audit_event_type"),
        Index("ix_developer_audit_event_application_created", "application_id", "created_at"),
    )

    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("developer_applications.id", ondelete="CASCADE"), nullable=False)
    credential_id: Mapped[UUID | None] = mapped_column(ForeignKey("api_client_credentials.id", ondelete="SET NULL"), nullable=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
