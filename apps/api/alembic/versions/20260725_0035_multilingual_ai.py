"""multilingual ai alignment

Revision ID: 20260725_0035
Revises: 20260725_0034
"""
from alembic import op
import sqlalchemy as sa
revision = "20260725_0035"
down_revision = "20260725_0034"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("ai_language_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("primary_language", sa.String(20), nullable=False), sa.Column("secondary_language", sa.String(20)),
        sa.Column("reading_level", sa.String(16), nullable=False, server_default="standard"), sa.Column("prefer_transliteration", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_ai_language_profile_user"),
        sa.CheckConstraint("primary_language IN ('ar','en','ur','hi','transliteration')", name="ck_ai_language_profile_primary"),
        sa.CheckConstraint("reading_level IN ('simple','standard','scholarly')", name="ck_ai_language_profile_level"))
    op.create_table("ai_translation_runs",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("orchestration_run_id", sa.Uuid(), sa.ForeignKey("ai_orchestration_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_language", sa.String(20), nullable=False), sa.Column("target_language", sa.String(20), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False), sa.Column("target_sha256", sa.String(64), nullable=False),
        sa.Column("claim_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("status", sa.String(20), nullable=False, server_default="received"),
        sa.Column("policy_version", sa.String(64), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source_language IN ('ar','en','ur','hi','transliteration')", name="ck_ai_translation_source_language"),
        sa.CheckConstraint("target_language IN ('ar','en','ur','hi','transliteration')", name="ck_ai_translation_target_language"),
        sa.CheckConstraint("status IN ('received','aligned','review_required','blocked','approved')", name="ck_ai_translation_status"),
        sa.CheckConstraint("claim_count >= 0", name="ck_ai_translation_claim_count"))
    op.create_index("ix_ai_translation_run_status_created", "ai_translation_runs", ["status", "created_at"])
    op.create_table("ai_claim_language_alignments",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("translation_run_id", sa.Uuid(), sa.ForeignKey("ai_translation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim_verification_id", sa.Uuid(), sa.ForeignKey("ai_claim_verifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_text_sha256", sa.String(64), nullable=False), sa.Column("target_text_sha256", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Numeric(5,4), nullable=False), sa.Column("citations_preserved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("decision", sa.String(16), nullable=False), sa.Column("reason_code", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("translation_run_id", "claim_verification_id", name="uq_ai_claim_language_alignment_claim"),
        sa.CheckConstraint("decision IN ('approved','review','blocked')", name="ck_ai_claim_language_alignment_decision"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_ai_claim_language_alignment_confidence"))
    op.create_table("ai_language_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("translation_run_id", sa.Uuid(), sa.ForeignKey("ai_translation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("review_type", sa.String(24), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"), sa.Column("reason_code", sa.String(80), nullable=False), sa.Column("review_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('queued','assigned','approved','rejected')", name="ck_ai_language_review_status"),
        sa.CheckConstraint("review_type IN ('language','translation','terminology','religious_meaning')", name="ck_ai_language_review_type"))
    op.create_index("ix_ai_language_review_queue", "ai_language_reviews", ["status", "review_type", "created_at"])

def downgrade():
    op.drop_table("ai_language_reviews"); op.drop_table("ai_claim_language_alignments"); op.drop_table("ai_translation_runs"); op.drop_table("ai_language_profiles")
