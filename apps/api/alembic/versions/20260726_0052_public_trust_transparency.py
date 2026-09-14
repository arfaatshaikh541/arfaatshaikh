"""Milestone 13

Revision ID: 20260726_0052
Revises: 20260726_0051
"""
from alembic import op
import sqlalchemy as sa

def _ts(): return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())]

revision="20260726_0052"
down_revision="20260726_0051"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("public_transparency_reports", sa.Column("id",sa.Uuid(),primary_key=True), sa.Column("institution_id",sa.Uuid(),sa.ForeignKey("institutions.id",ondelete="CASCADE"),nullable=False), sa.Column("report_version",sa.String(40),nullable=False), sa.Column("fingerprint_sha256",sa.String(64),nullable=False), sa.Column("source_coverage_percent",sa.Integer(),nullable=False), sa.Column("unresolved_high_risk_claims",sa.Integer(),nullable=False,server_default="0"), sa.Column("metrics_json",sa.JSON(),nullable=False,server_default="{}"), sa.Column("status",sa.String(16),nullable=False,server_default="draft"), *_ts(), sa.CheckConstraint("status IN ('draft','published','corrected','withdrawn')",name="ck_public_transparency_report_status"), sa.UniqueConstraint("institution_id","report_version",name="uq_public_transparency_report_version"))
    op.create_table("public_correction_cases", sa.Column("id",sa.Uuid(),primary_key=True), sa.Column("institution_id",sa.Uuid(),sa.ForeignKey("institutions.id",ondelete="CASCADE"),nullable=False), sa.Column("severity",sa.String(16),nullable=False), sa.Column("status",sa.String(16),nullable=False,server_default="open"), sa.Column("evidence_sha256",sa.String(64),nullable=False), sa.Column("affected_content_types_json",sa.JSON(),nullable=False,server_default="[]"), sa.Column("summary",sa.Text(),nullable=False), sa.Column("user_notification_planned",sa.Boolean(),nullable=False,server_default=sa.false()), *_ts(), sa.CheckConstraint("severity IN ('low','medium','high','critical')",name="ck_public_correction_case_severity"), sa.CheckConstraint("status IN ('open','review','approved','released','rejected')",name="ck_public_correction_case_status"))
    op.create_table("public_trust_incidents", sa.Column("id",sa.Uuid(),primary_key=True), sa.Column("institution_id",sa.Uuid(),sa.ForeignKey("institutions.id",ondelete="CASCADE"),nullable=False), sa.Column("severity",sa.String(16),nullable=False), sa.Column("status",sa.String(16),nullable=False,server_default="open"), sa.Column("evidence_sha256",sa.String(64),nullable=False), sa.Column("public_notice_url",sa.String(500)), sa.Column("summary",sa.Text(),nullable=False), *_ts(), sa.CheckConstraint("status IN ('open','contained','resolved','dismissed')",name="ck_public_trust_incident_status"))
    op.create_table("transparency_audit_events", sa.Column("id",sa.Uuid(),primary_key=True), sa.Column("institution_id",sa.Uuid(),sa.ForeignKey("institutions.id",ondelete="CASCADE"),nullable=False), sa.Column("sequence_number",sa.Integer(),nullable=False), sa.Column("event_type",sa.String(60),nullable=False), sa.Column("evidence_sha256",sa.String(64),nullable=False), sa.Column("previous_sha256",sa.String(64)), sa.Column("event_sha256",sa.String(64),nullable=False), sa.Column("metadata_json",sa.JSON(),nullable=False,server_default="{}"), *_ts(), sa.UniqueConstraint("institution_id","sequence_number",name="uq_transparency_audit_sequence"))
def downgrade():
    op.drop_table("transparency_audit_events"); op.drop_table("public_trust_incidents"); op.drop_table("public_correction_cases"); op.drop_table("public_transparency_reports")
