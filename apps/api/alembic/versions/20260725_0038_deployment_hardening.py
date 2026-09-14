"""deployment hardening and release verification

Revision ID: 20260725_0038
Revises: 20260725_0037
"""
from alembic import op
import sqlalchemy as sa
revision = "20260725_0038"
down_revision = "20260725_0037"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("deployment_environments",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("environment", sa.String(24), nullable=False), sa.Column("region", sa.String(80), nullable=False), sa.Column("public_base_url", sa.String(500), nullable=False), sa.Column("secrets_provider", sa.String(80), nullable=False), sa.Column("immutable_images_required", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("backups_required", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("environment IN ('development','test','staging','production')", name="ck_deployment_environment_name"), sa.UniqueConstraint("environment", name="uq_deployment_environment_name"))
    op.create_table("deployment_releases",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("environment_id", sa.Uuid(), sa.ForeignKey("deployment_environments.id", ondelete="RESTRICT"), nullable=False), sa.Column("release_version", sa.String(120), nullable=False), sa.Column("image_digest", sa.String(160), nullable=False), sa.Column("migration_revision", sa.String(80), nullable=False), sa.Column("status", sa.String(24), nullable=False, server_default="draft"), sa.Column("approved_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True), sa.Column("release_manifest", sa.JSON(), nullable=False, server_default="{}"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("status IN ('draft','approved','deploying','healthy','failed','rolled_back')", name="ck_deployment_release_status"))
    op.create_index("ix_deployment_release_environment_created", "deployment_releases", ["environment_id", "created_at"])
    op.create_table("deployment_verifications",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("release_id", sa.Uuid(), sa.ForeignKey("deployment_releases.id", ondelete="CASCADE"), nullable=False), sa.Column("check_type", sa.String(24), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("details", sa.JSON(), nullable=False, server_default="{}"), sa.Column("verified_by", sa.String(160), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("check_type IN ('config','secrets','migration','health','readiness','backup','rollback')", name="ck_deployment_verification_type"), sa.CheckConstraint("status IN ('passed','failed','blocked')", name="ck_deployment_verification_status"), sa.UniqueConstraint("release_id", "check_type", name="uq_deployment_verification_release_check"))
    op.create_table("backup_restore_rehearsals",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("environment_id", sa.Uuid(), sa.ForeignKey("deployment_environments.id", ondelete="CASCADE"), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="scheduled"), sa.Column("encrypted_backup_verified", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("restore_time_seconds", sa.Integer(), nullable=False, server_default="0"), sa.Column("recovery_point", sa.String(120), nullable=True), sa.Column("evidence_uri", sa.Text(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("status IN ('scheduled','running','passed','failed')", name="ck_backup_restore_rehearsal_status"), sa.CheckConstraint("restore_time_seconds >= 0", name="ck_backup_restore_time_nonnegative"))
    op.create_index("ix_backup_restore_environment_created", "backup_restore_rehearsals", ["environment_id", "created_at"])

def downgrade():
    op.drop_table("backup_restore_rehearsals"); op.drop_table("deployment_verifications"); op.drop_table("deployment_releases"); op.drop_table("deployment_environments")
