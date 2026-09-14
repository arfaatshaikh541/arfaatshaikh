"""Milestone 13

Revision ID: 20260726_0050
Revises: 20260726_0049
"""
from alembic import op
import sqlalchemy as sa

def _ts(): return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())]

revision="20260726_0050"
down_revision="20260726_0049"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("institutions", sa.Column("id",sa.Uuid(),primary_key=True), sa.Column("organisation_id",sa.Uuid(),sa.ForeignKey("organisations.id",ondelete="CASCADE"),nullable=False), sa.Column("slug",sa.String(120),nullable=False), sa.Column("legal_name",sa.String(240),nullable=False), sa.Column("institution_type",sa.String(32),nullable=False), sa.Column("country_code",sa.String(2),nullable=False), sa.Column("website_url",sa.String(500),nullable=False), sa.Column("verification_evidence_sha256",sa.String(64),nullable=False), sa.Column("status",sa.String(16),nullable=False,server_default="applicant"), *_ts(), sa.CheckConstraint("status IN ('applicant','verified','suspended','revoked')",name="ck_institution_status"), sa.UniqueConstraint("organisation_id","slug",name="uq_institution_org_slug"))
    op.create_index("ix_institution_country_status","institutions",["country_code","status"])
    op.create_table("institution_accreditations", sa.Column("id",sa.Uuid(),primary_key=True), sa.Column("institution_id",sa.Uuid(),sa.ForeignKey("institutions.id",ondelete="CASCADE"),nullable=False), sa.Column("accreditation_type",sa.String(40),nullable=False), sa.Column("version",sa.String(40),nullable=False), sa.Column("evidence_sha256",sa.String(64),nullable=False), sa.Column("reviewer_id",sa.Uuid(),sa.ForeignKey("users.id",ondelete="SET NULL")), sa.Column("expires_in_days",sa.Integer(),nullable=False), sa.Column("status",sa.String(16),nullable=False,server_default="pending"), *_ts(), sa.CheckConstraint("status IN ('pending','active','expired','revoked')",name="ck_institution_accreditation_status"), sa.UniqueConstraint("institution_id","accreditation_type","version",name="uq_institution_accreditation_version"))
    op.create_table("institution_portals", sa.Column("id",sa.Uuid(),primary_key=True), sa.Column("institution_id",sa.Uuid(),sa.ForeignKey("institutions.id",ondelete="CASCADE"),nullable=False), sa.Column("slug",sa.String(120),nullable=False), sa.Column("locale",sa.String(16),nullable=False), sa.Column("domain_url",sa.String(500),nullable=False), sa.Column("content_types_json",sa.JSON(),nullable=False,server_default="[]"), sa.Column("evidence_only",sa.Boolean(),nullable=False,server_default=sa.true()), sa.Column("status",sa.String(16),nullable=False,server_default="draft"), *_ts(), sa.CheckConstraint("status IN ('draft','review','published','suspended','retired')",name="ck_institution_portal_status"), sa.UniqueConstraint("institution_id","slug",name="uq_institution_portal_slug"))
    op.create_table("institution_governance_reviews", sa.Column("id",sa.Uuid(),primary_key=True), sa.Column("institution_id",sa.Uuid(),sa.ForeignKey("institutions.id",ondelete="CASCADE"),nullable=False), sa.Column("review_version",sa.String(40),nullable=False), sa.Column("outcome",sa.String(16),nullable=False,server_default="pending"), sa.Column("evidence_sha256",sa.String(64),nullable=False), sa.Column("controls_json",sa.JSON(),nullable=False,server_default="{}"), *_ts(), sa.CheckConstraint("outcome IN ('pending','passed','failed','conditional')",name="ck_institution_governance_review_outcome"))
def downgrade():
    op.drop_table("institution_governance_reviews"); op.drop_table("institution_portals"); op.drop_table("institution_accreditations"); op.drop_index("ix_institution_country_status",table_name="institutions"); op.drop_table("institutions")
