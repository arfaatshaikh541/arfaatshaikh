"""compliance governance disaster recovery and enterprise readiness

Revision ID: 20260725_0040
Revises: 20260725_0039
"""
from alembic import op
import sqlalchemy as sa
revision = "20260725_0040"
down_revision = "20260725_0039"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("compliance_frameworks",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("code", sa.String(40), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("version", sa.String(40), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="draft"), sa.Column("jurisdiction", sa.String(80), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("status IN ('draft','active','retired')", name="ck_compliance_framework_status"), sa.UniqueConstraint("code", "version", name="uq_compliance_framework_code_version"))
    op.create_table("compliance_controls",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("framework_id", sa.Uuid(), sa.ForeignKey("compliance_frameworks.id", ondelete="CASCADE"), nullable=False), sa.Column("control_key", sa.String(80), nullable=False), sa.Column("title", sa.String(240), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True), sa.Column("status", sa.String(24), nullable=False, server_default="planned"), sa.Column("test_frequency_days", sa.Integer(), nullable=False, server_default="365"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("status IN ('planned','implemented','tested','failed','not_applicable')", name="ck_compliance_control_status"), sa.UniqueConstraint("framework_id", "control_key", name="uq_compliance_control_framework_key"))
    op.create_index("ix_compliance_control_framework_status", "compliance_controls", ["framework_id", "status"])
    op.create_table("compliance_evidence",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("control_id", sa.Uuid(), sa.ForeignKey("compliance_controls.id", ondelete="CASCADE"), nullable=False), sa.Column("evidence_type", sa.String(80), nullable=False), sa.Column("uri", sa.Text(), nullable=False), sa.Column("sha256", sa.String(64), nullable=False), sa.Column("classification", sa.String(20), nullable=False, server_default="internal"), sa.Column("retention_days", sa.Integer(), nullable=False, server_default="365"), sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("classification IN ('public','internal','confidential','restricted')", name="ck_compliance_evidence_classification"), sa.CheckConstraint("retention_days BETWEEN 1 AND 3650", name="ck_compliance_evidence_retention"))
    op.create_index("ix_compliance_evidence_control_created", "compliance_evidence", ["control_id", "created_at"])
    op.create_table("enterprise_risks",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("risk_key", sa.String(80), nullable=False, unique=True), sa.Column("title", sa.String(240), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("likelihood", sa.Integer(), nullable=False), sa.Column("impact", sa.Integer(), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="open"), sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True), sa.Column("treatment_plan", sa.Text(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("likelihood BETWEEN 1 AND 5", name="ck_enterprise_risk_likelihood"), sa.CheckConstraint("impact BETWEEN 1 AND 5", name="ck_enterprise_risk_impact"), sa.CheckConstraint("status IN ('open','mitigating','accepted','closed')", name="ck_enterprise_risk_status"))
    op.create_index("ix_enterprise_risk_status", "enterprise_risks", ["status"])
    op.create_table("disaster_recovery_plans",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("environment_id", sa.Uuid(), sa.ForeignKey("deployment_environments.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="draft"), sa.Column("rpo_minutes", sa.Integer(), nullable=False), sa.Column("rto_minutes", sa.Integer(), nullable=False), sa.Column("multi_region", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("encrypted_backups", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("last_test_evidence", sa.JSON(), nullable=False, server_default="{}"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("status IN ('draft','approved','tested','failed','retired')", name="ck_disaster_recovery_plan_status"), sa.CheckConstraint("rpo_minutes >= 0", name="ck_disaster_recovery_plan_rpo"), sa.CheckConstraint("rto_minutes > 0", name="ck_disaster_recovery_plan_rto"), sa.UniqueConstraint("environment_id", "name", name="uq_disaster_recovery_plan_environment_name"))

def downgrade():
    op.drop_table("disaster_recovery_plans"); op.drop_table("enterprise_risks"); op.drop_table("compliance_evidence"); op.drop_table("compliance_controls"); op.drop_table("compliance_frameworks")
