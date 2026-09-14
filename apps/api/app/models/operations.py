from __future__ import annotations
from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class OperationalAlertRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "operational_alert_rules"
    __table_args__ = (
        CheckConstraint("severity IN ('info','warning','high','critical')", name="ck_operational_alert_rule_severity"),
        CheckConstraint("evaluation_window_seconds >= 60", name="ck_operational_alert_window"),
        UniqueConstraint("environment_id", "name", name="uq_operational_alert_rule_environment_name"),
    )
    environment_id: Mapped[UUID] = mapped_column(ForeignKey("deployment_environments.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(160), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    evaluation_window_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300, server_default="300")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    runbook_uri: Mapped[str] = mapped_column(Text, nullable=False)

class OperationalAlertEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "operational_alert_events"
    __table_args__ = (
        CheckConstraint("status IN ('open','acknowledged','resolved','suppressed')", name="ck_operational_alert_event_status"),
        Index("ix_operational_alert_event_rule_created", "rule_id", "created_at"),
    )
    rule_id: Mapped[UUID] = mapped_column(ForeignKey("operational_alert_rules.id", ondelete="RESTRICT"), nullable=False)
    release_id: Mapped[UUID | None] = mapped_column(ForeignKey("deployment_releases.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", server_default="open")
    observed_value: Mapped[int] = mapped_column(Integer, nullable=False)
    correlation_key: Mapped[str] = mapped_column(String(180), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")

class OperationalIncident(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "operational_incidents"
    __table_args__ = (
        CheckConstraint("severity IN ('sev1','sev2','sev3','sev4')", name="ck_operational_incident_severity"),
        CheckConstraint("status IN ('declared','investigating','mitigated','resolved','closed')", name="ck_operational_incident_status"),
        Index("ix_operational_incident_environment_created", "environment_id", "created_at"),
    )
    environment_id: Mapped[UUID] = mapped_column(ForeignKey("deployment_environments.id", ondelete="RESTRICT"), nullable=False)
    release_id: Mapped[UUID | None] = mapped_column(ForeignKey("deployment_releases.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    severity: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="declared", server_default="declared")
    commander_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    customer_impact: Mapped[str] = mapped_column(Text, nullable=False)
    timeline: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)

class RunbookExecution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "runbook_executions"
    __table_args__ = (
        CheckConstraint("status IN ('started','passed','failed','aborted')", name="ck_runbook_execution_status"),
        CheckConstraint("duration_seconds >= 0", name="ck_runbook_execution_duration"),
        Index("ix_runbook_execution_incident_created", "incident_id", "created_at"),
    )
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("operational_incidents.id", ondelete="CASCADE"), nullable=False)
    runbook_key: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="started", server_default="started")
    executed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    rollback_performed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
