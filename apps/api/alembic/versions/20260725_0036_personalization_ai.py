"""personalization and accessibility governance

Revision ID: 20260725_0036
Revises: 20260725_0035
"""
from alembic import op
import sqlalchemy as sa
revision = "20260725_0036"
down_revision = "20260725_0035"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("ai_personalization_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reading_depth", sa.String(16), nullable=False, server_default="standard"), sa.Column("recommendation_mode", sa.String(16), nullable=False, server_default="standard"),
        sa.Column("preferred_topics", sa.JSON(), nullable=False, server_default="[]"), sa.Column("hidden_topics", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("personalization_enabled", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_ai_personalization_profile_user"), sa.CheckConstraint("reading_depth IN ('concise','standard','detailed','scholarly')", name="ck_ai_personalization_depth"), sa.CheckConstraint("recommendation_mode IN ('off','minimal','standard')", name="ck_ai_personalization_mode"))
    op.create_table("ai_accessibility_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("text_scale_percent", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("reduced_motion", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("high_contrast", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("screen_reader_optimised", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("captions_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("user_id", name="uq_ai_accessibility_profile_user"), sa.CheckConstraint("text_scale_percent >= 75 AND text_scale_percent <= 200", name="ck_ai_accessibility_text_scale"))
    op.create_table("ai_personalization_events",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("event_type", sa.String(32), nullable=False), sa.Column("subject_key", sa.String(200), nullable=False), sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"), sa.Column("consent_basis", sa.String(40), nullable=False), sa.Column("retention_days", sa.Integer(), nullable=False, server_default="90"), sa.Column("eligible_for_recommendation", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("event_type IN ('explicit_preference','course_progress','bookmark','dismissal','language_choice','accessibility_change')", name="ck_ai_personalization_event_type"), sa.CheckConstraint("retention_days >= 0 AND retention_days <= 365", name="ck_ai_personalization_retention"))
    op.create_index("ix_ai_personalization_event_user_created", "ai_personalization_events", ["user_id", "created_at"])
    op.create_table("ai_recommendation_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("candidate_key", sa.String(200), nullable=False), sa.Column("decision", sa.String(16), nullable=False), sa.Column("score", sa.Integer(), nullable=False), sa.Column("reason_codes", sa.JSON(), nullable=False, server_default="[]"), sa.Column("policy_version", sa.String(64), nullable=False), sa.Column("explanation", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("decision IN ('recommended','suppressed','blocked')", name="ck_ai_recommendation_decision"), sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_ai_recommendation_score"))
    op.create_index("ix_ai_recommendation_user_created", "ai_recommendation_decisions", ["user_id", "created_at"])

def downgrade():
    op.drop_table("ai_recommendation_decisions"); op.drop_table("ai_personalization_events"); op.drop_table("ai_accessibility_profiles"); op.drop_table("ai_personalization_profiles")
