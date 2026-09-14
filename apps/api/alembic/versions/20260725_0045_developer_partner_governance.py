"""developer partner governance and integration certification

Revision ID: 20260725_0045
Revises: 20260725_0044
"""
from alembic import op
import sqlalchemy as sa

revision = "20260725_0045"
down_revision = "20260725_0044"
branch_labels = None
depends_on = None


def _timestamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())]


def upgrade():
    op.create_table("developer_partners", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("organisation_id", sa.Uuid(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="applicant"), sa.Column("legal_name", sa.String(200), nullable=False), sa.Column("website_url", sa.String(500), nullable=False), sa.Column("privacy_contact", sa.String(254), nullable=False), sa.Column("terms_accepted", sa.Boolean(), nullable=False, server_default=sa.false()), *_timestamps(), sa.CheckConstraint("status IN ('applicant','verified','suspended','revoked')", name="ck_developer_partner_status"), sa.UniqueConstraint("organisation_id", name="uq_developer_partner_organisation"))
    op.create_table("integration_listings", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("partner_id", sa.Uuid(), sa.ForeignKey("developer_partners.id", ondelete="CASCADE"), nullable=False), sa.Column("application_id", sa.Uuid(), sa.ForeignKey("developer_applications.id", ondelete="RESTRICT"), nullable=False), sa.Column("slug", sa.String(100), nullable=False), sa.Column("name", sa.String(180), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("requested_scopes", sa.JSON(), nullable=False, server_default="[]"), sa.Column("status", sa.String(20), nullable=False, server_default="draft"), sa.Column("support_url", sa.String(500), nullable=False), *_timestamps(), sa.CheckConstraint("status IN ('draft','review','published','suspended','retired')", name="ck_integration_listing_status"), sa.UniqueConstraint("slug", name="uq_integration_listing_slug"))
    op.create_index("ix_integration_listing_partner_status", "integration_listings", ["partner_id", "status"])
    op.create_table("integration_security_reviews", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("listing_id", sa.Uuid(), sa.ForeignKey("integration_listings.id", ondelete="CASCADE"), nullable=False), sa.Column("reviewer_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="pending"), sa.Column("evidence_sha256", sa.String(64), nullable=False), sa.Column("critical_findings", sa.Integer(), nullable=False, server_default="0"), sa.Column("high_findings", sa.Integer(), nullable=False, server_default="0"), sa.Column("data_minimisation_verified", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("deletion_verified", sa.Boolean(), nullable=False, server_default=sa.false()), *_timestamps(), sa.CheckConstraint("status IN ('pending','passed','failed','expired')", name="ck_integration_security_review_status"), sa.CheckConstraint("critical_findings >= 0 AND high_findings >= 0", name="ck_integration_security_review_findings"))
    op.create_index("ix_integration_security_review_listing_status", "integration_security_reviews", ["listing_id", "status"])
    op.create_table("integration_certifications", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("listing_id", sa.Uuid(), sa.ForeignKey("integration_listings.id", ondelete="CASCADE"), nullable=False), sa.Column("security_review_id", sa.Uuid(), sa.ForeignKey("integration_security_reviews.id", ondelete="RESTRICT"), nullable=False), sa.Column("certificate_version", sa.String(32), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="active"), sa.Column("expires_at_iso", sa.String(40), nullable=False), sa.Column("certification_sha256", sa.String(64), nullable=False), *_timestamps(), sa.CheckConstraint("status IN ('active','expired','revoked')", name="ck_integration_certification_status"), sa.UniqueConstraint("listing_id", "certificate_version", name="uq_integration_certification_listing_version"))
    op.create_table("partner_security_incidents", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("partner_id", sa.Uuid(), sa.ForeignKey("developer_partners.id", ondelete="CASCADE"), nullable=False), sa.Column("listing_id", sa.Uuid(), sa.ForeignKey("integration_listings.id", ondelete="SET NULL"), nullable=True), sa.Column("severity", sa.String(16), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="open"), sa.Column("summary", sa.Text(), nullable=False), sa.Column("evidence_sha256", sa.String(64), nullable=False), sa.Column("credentials_revoked", sa.Boolean(), nullable=False, server_default=sa.false()), *_timestamps(), sa.CheckConstraint("severity IN ('low','medium','high','critical')", name="ck_partner_security_incident_severity"), sa.CheckConstraint("status IN ('open','contained','resolved')", name="ck_partner_security_incident_status"))
    op.create_index("ix_partner_security_incident_partner_status", "partner_security_incidents", ["partner_id", "status"])


def downgrade():
    op.drop_table("partner_security_incidents")
    op.drop_table("integration_certifications")
    op.drop_table("integration_security_reviews")
    op.drop_table("integration_listings")
    op.drop_table("developer_partners")
