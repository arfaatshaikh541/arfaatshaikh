"""developer access and usage governance

Revision ID: 20260725_0043
Revises: 20260725_0042
"""
from alembic import op
import sqlalchemy as sa

revision = "20260725_0043"
down_revision = "20260725_0042"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("api_access_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("organisation_id", sa.Uuid(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False), sa.Column("application_id", sa.Uuid(), sa.ForeignKey("developer_applications.id", ondelete="CASCADE"), nullable=False), sa.Column("credential_id", sa.Uuid(), sa.ForeignKey("api_client_credentials.id", ondelete="CASCADE"), nullable=False), sa.Column("request_id", sa.String(80), nullable=False), sa.Column("route_template", sa.String(180), nullable=False), sa.Column("required_scope", sa.String(80), nullable=False), sa.Column("decision", sa.String(8), nullable=False), sa.Column("response_status_code", sa.Integer(), nullable=False), sa.Column("reason_codes", sa.JSON(), nullable=False, server_default="[]"), sa.Column("client_ip_hash", sa.String(64), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("decision IN ('allow','deny')", name="ck_api_access_decision_result"), sa.CheckConstraint("response_status_code >= 100 AND response_status_code <= 599", name="ck_api_access_decision_status_code"))
    op.create_index("ix_api_access_decision_credential_created", "api_access_decisions", ["credential_id", "created_at"])
    op.create_index("ix_api_access_decision_org_created", "api_access_decisions", ["organisation_id", "created_at"])
    op.create_table("api_usage_records",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("organisation_id", sa.Uuid(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False), sa.Column("application_id", sa.Uuid(), sa.ForeignKey("developer_applications.id", ondelete="CASCADE"), nullable=False), sa.Column("credential_id", sa.Uuid(), sa.ForeignKey("api_client_credentials.id", ondelete="CASCADE"), nullable=False), sa.Column("request_id", sa.String(80), nullable=False), sa.Column("idempotency_key", sa.String(128), nullable=False), sa.Column("route_template", sa.String(180), nullable=False), sa.Column("response_status_code", sa.Integer(), nullable=False), sa.Column("billable_units", sa.Integer(), nullable=False, server_default="1"), sa.Column("usage_metadata", sa.JSON(), nullable=False, server_default="{}"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("billable_units >= 0", name="ck_api_usage_record_units"), sa.CheckConstraint("response_status_code >= 100 AND response_status_code <= 599", name="ck_api_usage_record_status_code"), sa.UniqueConstraint("credential_id", "idempotency_key", name="uq_api_usage_record_credential_idempotency"))
    op.create_index("ix_api_usage_record_credential_created", "api_usage_records", ["credential_id", "created_at"])
    op.create_table("api_quota_windows",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("credential_id", sa.Uuid(), sa.ForeignKey("api_client_credentials.id", ondelete="CASCADE"), nullable=False), sa.Column("window_key", sa.String(80), nullable=False), sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("limit_count", sa.Integer(), nullable=False), sa.Column("resets_at_iso", sa.String(40), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("request_count >= 0", name="ck_api_quota_window_count"), sa.CheckConstraint("limit_count > 0", name="ck_api_quota_window_limit"), sa.UniqueConstraint("credential_id", "window_key", name="uq_api_quota_window_credential_window"))
    op.create_index("ix_api_quota_window_credential", "api_quota_windows", ["credential_id"])
    op.create_table("developer_audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("organisation_id", sa.Uuid(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False), sa.Column("application_id", sa.Uuid(), sa.ForeignKey("developer_applications.id", ondelete="CASCADE"), nullable=False), sa.Column("credential_id", sa.Uuid(), sa.ForeignKey("api_client_credentials.id", ondelete="SET NULL"), nullable=True), sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True), sa.Column("event_type", sa.String(40), nullable=False), sa.Column("summary", sa.Text(), nullable=False), sa.Column("evidence_sha256", sa.String(64), nullable=False), sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("event_type IN ('credential.used','credential.denied','quota.exceeded','credential.rotated','credential.revoked','scope.changed')", name="ck_developer_audit_event_type"))
    op.create_index("ix_developer_audit_event_application_created", "developer_audit_events", ["application_id", "created_at"])


def downgrade():
    op.drop_table("developer_audit_events")
    op.drop_table("api_quota_windows")
    op.drop_table("api_usage_records")
    op.drop_table("api_access_decisions")
