"""developer platform foundation

Revision ID: 20260725_0042
Revises: 20260725_0041
"""
from alembic import op
import sqlalchemy as sa
revision = "20260725_0042"
down_revision = "20260725_0041"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("developer_applications",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("organisation_id", sa.Uuid(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False), sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("slug", sa.String(80), nullable=False), sa.Column("application_type", sa.String(20), nullable=False, server_default="partner"), sa.Column("status", sa.String(16), nullable=False, server_default="draft"), sa.Column("privacy_policy_url", sa.Text(), nullable=True), sa.Column("terms_url", sa.Text(), nullable=True), sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("status IN ('draft','active','suspended','revoked')", name="ck_developer_application_status"), sa.CheckConstraint("application_type IN ('first_party','partner','public')", name="ck_developer_application_type"), sa.UniqueConstraint("organisation_id", "slug", name="uq_developer_application_org_slug"))
    op.create_index("ix_developer_application_org_status", "developer_applications", ["organisation_id", "status"])
    op.create_table("api_client_credentials",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("application_id", sa.Uuid(), sa.ForeignKey("developer_applications.id", ondelete="CASCADE"), nullable=False), sa.Column("key_prefix", sa.String(20), nullable=False), sa.Column("secret_hash", sa.String(128), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="active"), sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False, server_default="60"), sa.Column("expires_at_iso", sa.String(40), nullable=True), sa.Column("last_used_at_iso", sa.String(40), nullable=True), sa.Column("rotated_from_id", sa.Uuid(), sa.ForeignKey("api_client_credentials.id", ondelete="SET NULL"), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("status IN ('active','rotating','revoked','expired')", name="ck_api_client_credential_status"), sa.CheckConstraint("rate_limit_per_minute > 0 AND rate_limit_per_minute <= 6000", name="ck_api_client_credential_rate_limit"), sa.UniqueConstraint("key_prefix", name="uq_api_client_credential_prefix"))
    op.create_index("ix_api_client_credential_application_status", "api_client_credentials", ["application_id", "status"])
    op.create_table("api_client_scopes",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("credential_id", sa.Uuid(), sa.ForeignKey("api_client_credentials.id", ondelete="CASCADE"), nullable=False), sa.Column("scope", sa.String(80), nullable=False), sa.Column("granted_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True), sa.Column("justification", sa.Text(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("credential_id", "scope", name="uq_api_client_scope_credential_scope"))
    op.create_index("ix_api_client_scope_scope", "api_client_scopes", ["scope"])
    op.create_table("webhook_subscriptions",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("application_id", sa.Uuid(), sa.ForeignKey("developer_applications.id", ondelete="CASCADE"), nullable=False), sa.Column("endpoint_url", sa.Text(), nullable=False), sa.Column("signing_secret_hash", sa.String(128), nullable=False), sa.Column("subscribed_events", sa.JSON(), nullable=False, server_default="[]"), sa.Column("status", sa.String(16), nullable=False, server_default="pending"), sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("last_verified_at_iso", sa.String(40), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("status IN ('pending','active','paused','failed','revoked')", name="ck_webhook_subscription_status"), sa.CheckConstraint("failure_count >= 0", name="ck_webhook_subscription_failure_count"), sa.UniqueConstraint("application_id", "endpoint_url", name="uq_webhook_subscription_application_endpoint"))
    op.create_index("ix_webhook_subscription_application_status", "webhook_subscriptions", ["application_id", "status"])
    op.create_table("webhook_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("subscription_id", sa.Uuid(), sa.ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"), nullable=False), sa.Column("event_id", sa.String(80), nullable=False), sa.Column("event_type", sa.String(80), nullable=False), sa.Column("payload_sha256", sa.String(64), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="queued"), sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("response_status_code", sa.Integer(), nullable=True), sa.Column("response_summary", sa.Text(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("status IN ('queued','delivering','delivered','retrying','failed','discarded')", name="ck_webhook_delivery_status"), sa.CheckConstraint("attempt_count >= 0 AND attempt_count <= 12", name="ck_webhook_delivery_attempt_count"), sa.UniqueConstraint("subscription_id", "event_id", name="uq_webhook_delivery_subscription_event"))
    op.create_index("ix_webhook_delivery_subscription_status", "webhook_deliveries", ["subscription_id", "status"])


def downgrade():
    op.drop_table("webhook_deliveries")
    op.drop_table("webhook_subscriptions")
    op.drop_table("api_client_scopes")
    op.drop_table("api_client_credentials")
    op.drop_table("developer_applications")
