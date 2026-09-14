"""Milestone 13

Revision ID: 20260726_0051
Revises: 20260726_0050
"""
from alembic import op
import sqlalchemy as sa

def _ts(): return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())]

revision="20260726_0051"
down_revision="20260726_0050"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("regional_data_policies", sa.Column("id",sa.Uuid(),primary_key=True), sa.Column("organisation_id",sa.Uuid(),sa.ForeignKey("organisations.id",ondelete="CASCADE"),nullable=False), sa.Column("region",sa.String(20),nullable=False), sa.Column("version",sa.String(40),nullable=False), sa.Column("storage_regions_json",sa.JSON(),nullable=False,server_default="[]"), sa.Column("processing_regions_json",sa.JSON(),nullable=False,server_default="[]"), sa.Column("cross_border_transfer",sa.Boolean(),nullable=False,server_default=sa.false()), sa.Column("transfer_basis",sa.String(40)), sa.Column("status",sa.String(16),nullable=False,server_default="draft"), *_ts(), sa.UniqueConstraint("organisation_id","region","version",name="uq_regional_data_policy_version"))
    op.create_table("localization_releases", sa.Column("id",sa.Uuid(),primary_key=True), sa.Column("portal_id",sa.Uuid(),sa.ForeignKey("institution_portals.id",ondelete="CASCADE"),nullable=False), sa.Column("locale",sa.String(16),nullable=False), sa.Column("release_version",sa.String(40),nullable=False), sa.Column("source_sha256",sa.String(64),nullable=False), sa.Column("translation_sha256",sa.String(64),nullable=False), sa.Column("semantic_alignment_score",sa.Integer(),nullable=False), sa.Column("content_type",sa.String(32),nullable=False), sa.Column("native_reviewer_id",sa.Uuid(),sa.ForeignKey("users.id",ondelete="SET NULL")), sa.Column("scholarly_reviewed",sa.Boolean(),nullable=False,server_default=sa.false()), sa.Column("status",sa.String(16),nullable=False,server_default="draft"), *_ts(), sa.CheckConstraint("status IN ('draft','review','published','rejected','superseded')",name="ck_localization_release_status"), sa.UniqueConstraint("portal_id","locale","release_version",name="uq_localization_release_version"))
    op.create_table("residency_assessments", sa.Column("id",sa.Uuid(),primary_key=True), sa.Column("data_policy_id",sa.Uuid(),sa.ForeignKey("regional_data_policies.id",ondelete="CASCADE"),nullable=False), sa.Column("outcome",sa.String(16),nullable=False,server_default="pending"), sa.Column("evidence_sha256",sa.String(64),nullable=False), sa.Column("findings_json",sa.JSON(),nullable=False,server_default="[]"), *_ts(), sa.CheckConstraint("outcome IN ('pending','passed','failed','conditional')",name="ck_residency_assessment_outcome"))
    op.create_table("regional_support_coverage", sa.Column("id",sa.Uuid(),primary_key=True), sa.Column("organisation_id",sa.Uuid(),sa.ForeignKey("organisations.id",ondelete="CASCADE"),nullable=False), sa.Column("region",sa.String(20),nullable=False), sa.Column("languages_json",sa.JSON(),nullable=False,server_default="[]"), sa.Column("coverage_hours",sa.Integer(),nullable=False,server_default="0"), sa.Column("escalation_available",sa.Boolean(),nullable=False,server_default=sa.false()), *_ts(), sa.UniqueConstraint("organisation_id","region",name="uq_regional_support_org_region"))
def downgrade():
    op.drop_table("regional_support_coverage"); op.drop_table("residency_assessments"); op.drop_table("localization_releases"); op.drop_table("regional_data_policies")
