"""developer ecosystem and version lifecycle

Revision ID: 20260725_0044
Revises: 20260725_0043
"""
from alembic import op
import sqlalchemy as sa

revision = "20260725_0044"
down_revision = "20260725_0043"
branch_labels = None
depends_on = None


def _timestamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())]


def upgrade():
    op.create_table("api_products", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("slug", sa.String(80), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("required_scope", sa.String(80), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="draft"), sa.Column("public_documentation", sa.Boolean(), nullable=False, server_default=sa.false()), *_timestamps(), sa.CheckConstraint("status IN ('draft','active','deprecated','retired')", name="ck_api_product_status"), sa.UniqueConstraint("slug", name="uq_api_product_slug"))
    op.create_table("api_versions", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("product_id", sa.Uuid(), sa.ForeignKey("api_products.id", ondelete="CASCADE"), nullable=False), sa.Column("version", sa.String(24), nullable=False), sa.Column("lifecycle_status", sa.String(20), nullable=False), sa.Column("specification_sha256", sa.String(64), nullable=False), sa.Column("changelog", sa.Text(), nullable=False), sa.Column("breaking_changes", sa.JSON(), nullable=False, server_default="[]"), sa.Column("sunset_notice_days", sa.Integer(), nullable=False, server_default="0"), sa.Column("successor_version", sa.String(24), nullable=True), *_timestamps(), sa.CheckConstraint("lifecycle_status IN ('preview','current','deprecated','retired')", name="ck_api_version_lifecycle"), sa.CheckConstraint("sunset_notice_days >= 0", name="ck_api_version_sunset_notice"), sa.UniqueConstraint("product_id", "version", name="uq_api_version_product_version"))
    op.create_index("ix_api_version_product_status", "api_versions", ["product_id", "lifecycle_status"])
    op.create_table("api_documentation_artifacts", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("api_version_id", sa.Uuid(), sa.ForeignKey("api_versions.id", ondelete="CASCADE"), nullable=False), sa.Column("artifact_type", sa.String(20), nullable=False), sa.Column("locale", sa.String(16), nullable=False, server_default="en"), sa.Column("content_uri", sa.String(500), nullable=False), sa.Column("content_sha256", sa.String(64), nullable=False), sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()), *_timestamps(), sa.CheckConstraint("artifact_type IN ('openapi','guide','example','changelog')", name="ck_api_documentation_artifact_type"), sa.UniqueConstraint("api_version_id", "artifact_type", "locale", name="uq_api_documentation_version_type_locale"))
    op.create_table("sdk_releases", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("api_version_id", sa.Uuid(), sa.ForeignKey("api_versions.id", ondelete="RESTRICT"), nullable=False), sa.Column("language", sa.String(20), nullable=False), sa.Column("version", sa.String(32), nullable=False), sa.Column("package_uri", sa.String(500), nullable=False), sa.Column("package_sha256", sa.String(64), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="draft"), sa.Column("tests_passed", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("provenance_verified", sa.Boolean(), nullable=False, server_default=sa.false()), *_timestamps(), sa.CheckConstraint("language IN ('python','typescript','java','dotnet')", name="ck_sdk_release_language"), sa.CheckConstraint("status IN ('draft','published','yanked')", name="ck_sdk_release_status"), sa.UniqueConstraint("language", "version", name="uq_sdk_release_language_version"))
    op.create_table("developer_sandbox_sessions", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("organisation_id", sa.Uuid(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False), sa.Column("application_id", sa.Uuid(), sa.ForeignKey("developer_applications.id", ondelete="CASCADE"), nullable=False), sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="active"), sa.Column("allowed_scopes", sa.JSON(), nullable=False, server_default="[]"), sa.Column("request_limit", sa.Integer(), nullable=False, server_default="100"), sa.Column("used_requests", sa.Integer(), nullable=False, server_default="0"), sa.Column("expires_at_iso", sa.String(40), nullable=False), *_timestamps(), sa.CheckConstraint("status IN ('active','expired','revoked')", name="ck_developer_sandbox_status"), sa.CheckConstraint("request_limit > 0 AND request_limit <= 1000", name="ck_developer_sandbox_limit"), sa.CheckConstraint("used_requests >= 0", name="ck_developer_sandbox_usage"))
    op.create_index("ix_developer_sandbox_application_status", "developer_sandbox_sessions", ["application_id", "status"])


def downgrade():
    op.drop_table("developer_sandbox_sessions")
    op.drop_table("sdk_releases")
    op.drop_table("api_documentation_artifacts")
    op.drop_table("api_versions")
    op.drop_table("api_products")
