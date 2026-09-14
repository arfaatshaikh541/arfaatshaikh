"""evidence grounded ai orchestration

Revision ID: 20260725_0034
Revises: 20260725_0033
"""
from alembic import op
import sqlalchemy as sa

revision = "20260725_0034"
down_revision = "20260725_0033"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_orchestration_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("question_sha256", sa.String(64), nullable=False),
        sa.Column("locale", sa.String(16), nullable=False),
        sa.Column("classification", sa.String(48), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="received"),
        sa.Column("orchestration_policy_version", sa.String(64), nullable=False),
        sa.Column("grounding_policy_version", sa.String(64), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requires_scholar", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("terminal_reason", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('received','classified','retrieving','grounding','blocked','escalated','completed','failed')", name="ck_ai_orchestration_run_status"),
        sa.CheckConstraint("risk_level IN ('standard','sensitive','high_risk')", name="ck_ai_orchestration_run_risk"),
        sa.CheckConstraint("evidence_count >= 0", name="ck_ai_orchestration_evidence_count"),
    )
    op.create_index("ix_ai_orchestration_user_created", "ai_orchestration_runs", ["user_id", "created_at"])

    op.create_table(
        "ai_claim_verifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("orchestration_run_id", sa.Uuid(), sa.ForeignKey("ai_orchestration_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("claim_type", sa.String(40), nullable=False),
        sa.Column("claim_text_sha256", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("citation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reason_code", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("orchestration_run_id", "position", name="uq_ai_claim_verification_position"),
        sa.CheckConstraint("claim_type IN ('direct_quote','source_summary','scholarly_interpretation','difference_of_opinion','general_explanation','ruling')", name="ck_ai_claim_verification_type"),
        sa.CheckConstraint("decision IN ('verified','blocked','escalated')", name="ck_ai_claim_verification_decision"),
        sa.CheckConstraint("position >= 0", name="ck_ai_claim_verification_position"),
    )

    op.create_table(
        "ai_claim_citations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("claim_verification_id", sa.Uuid(), sa.ForeignKey("ai_claim_verifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_passage_id", sa.Uuid(), sa.ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("retrieval_chunk_id", sa.Uuid(), sa.ForeignKey("retrieval_chunks.id", ondelete="SET NULL")),
        sa.Column("support_type", sa.String(20), nullable=False),
        sa.Column("evidence_sha256", sa.String(64), nullable=False),
        sa.Column("citation_label", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("claim_verification_id", "source_passage_id", "support_type", name="uq_ai_claim_citation_source"),
        sa.CheckConstraint("support_type IN ('quotes','supports','attributes','contrasts')", name="ck_ai_claim_citation_support"),
    )

    op.create_table(
        "ai_scholar_escalations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("orchestration_run_id", sa.Uuid(), sa.ForeignKey("ai_orchestration_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_scholar_profile_id", sa.Uuid(), sa.ForeignKey("scholar_profiles.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("priority", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("reason_code", sa.String(80), nullable=False),
        sa.Column("context_sha256", sa.String(64), nullable=False),
        sa.Column("resolution_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('queued','assigned','resolved','closed')", name="ck_ai_scholar_escalation_status"),
        sa.CheckConstraint("priority IN ('normal','high','urgent')", name="ck_ai_scholar_escalation_priority"),
    )
    op.create_index("ix_ai_scholar_escalation_status_priority", "ai_scholar_escalations", ["status", "priority", "created_at"])


def downgrade():
    op.drop_table("ai_scholar_escalations")
    op.drop_table("ai_claim_citations")
    op.drop_table("ai_claim_verifications")
    op.drop_table("ai_orchestration_runs")
