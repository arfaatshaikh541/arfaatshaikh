"""operations observability incident response and resilience

Revision ID: 20260725_0039
Revises: 20260725_0038
"""
from alembic import op
import sqlalchemy as sa
revision = "20260725_0039"
down_revision = "20260725_0038"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("operational_alert_rules",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("environment_id", sa.Uuid(), sa.ForeignKey("deployment_environments.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("metric_name", sa.String(160), nullable=False), sa.Column("severity", sa.String(16), nullable=False), sa.Column("threshold", sa.Integer(), nullable=False), sa.Column("evaluation_window_seconds", sa.Integer(), nullable=False, server_default="300"), sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("runbook_uri", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("severity IN ('info','warning','high','critical')", name="ck_operational_alert_rule_severity"), sa.CheckConstraint("evaluation_window_seconds >= 60", name="ck_operational_alert_window"), sa.UniqueConstraint("environment_id", "name", name="uq_operational_alert_rule_environment_name"))
    op.create_table("operational_alert_events",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("rule_id", sa.Uuid(), sa.ForeignKey("operational_alert_rules.id", ondelete="RESTRICT"), nullable=False), sa.Column("release_id", sa.Uuid(), sa.ForeignKey("deployment_releases.id", ondelete="SET NULL"), nullable=True), sa.Column("status", sa.String(20), nullable=False, server_default="open"), sa.Column("observed_value", sa.Integer(), nullable=False), sa.Column("correlation_key", sa.String(180), nullable=False), sa.Column("evidence", sa.JSON(), nullable=False, server_default="{}"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("status IN ('open','acknowledged','resolved','suppressed')", name="ck_operational_alert_event_status"))
    op.create_index("ix_operational_alert_event_rule_created", "operational_alert_events", ["rule_id", "created_at"])
    op.create_table("operational_incidents",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("environment_id", sa.Uuid(), sa.ForeignKey("deployment_environments.id", ondelete="RESTRICT"), nullable=False), sa.Column("release_id", sa.Uuid(), sa.ForeignKey("deployment_releases.id", ondelete="SET NULL"), nullable=True), sa.Column("title", sa.String(240), nullable=False), sa.Column("severity", sa.String(8), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="declared"), sa.Column("commander_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True), sa.Column("customer_impact", sa.Text(), nullable=False), sa.Column("timeline", sa.JSON(), nullable=False, server_default="[]"), sa.Column("root_cause", sa.Text(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("severity IN ('sev1','sev2','sev3','sev4')", name="ck_operational_incident_severity"), sa.CheckConstraint("status IN ('declared','investigating','mitigated','resolved','closed')", name="ck_operational_incident_status"))
    op.create_index("ix_operational_incident_environment_created", "operational_incidents", ["environment_id", "created_at"])
    op.create_table("runbook_executions",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("incident_id", sa.Uuid(), sa.ForeignKey("operational_incidents.id", ondelete="CASCADE"), nullable=False), sa.Column("runbook_key", sa.String(160), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="started"), sa.Column("executed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True), sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"), sa.Column("steps", sa.JSON(), nullable=False, server_default="[]"), sa.Column("rollback_performed", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("status IN ('started','passed','failed','aborted')", name="ck_runbook_execution_status"), sa.CheckConstraint("duration_seconds >= 0", name="ck_runbook_execution_duration"))
    op.create_index("ix_runbook_execution_incident_created", "runbook_executions", ["incident_id", "created_at"])

def downgrade():
    op.drop_table("runbook_executions"); op.drop_table("operational_incidents"); op.drop_table("operational_alert_events"); op.drop_table("operational_alert_rules")
