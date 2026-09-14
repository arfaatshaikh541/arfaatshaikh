"""add tafsir cross-reference and topic graph

Revision ID: 20260725_0020
Revises: 20260725_0019
"""
from alembic import op
import sqlalchemy as sa

revision = "20260725_0020"
down_revision = "20260725_0019"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("knowledge_topics",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("topic_key", sa.String(120), nullable=False), sa.Column("parent_topic_id", sa.Uuid(), nullable=True), sa.Column("english_name", sa.String(240), nullable=False), sa.Column("arabic_name", sa.String(240), nullable=False), sa.Column("description", sa.Text(), nullable=True), sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False), sa.Column("source_passage_id", sa.Uuid(), nullable=False), sa.Column("published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint("sort_order >= 0", name="ck_knowledge_topics_sort_order"), sa.ForeignKeyConstraint(["parent_topic_id"], ["knowledge_topics.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["source_passage_id"], ["source_passages.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("topic_key"))
    op.create_index("ix_knowledge_topics_parent_topic_id", "knowledge_topics", ["parent_topic_id"])
    op.create_table("knowledge_topic_aliases",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("topic_id", sa.Uuid(), nullable=False), sa.Column("language", sa.String(16), nullable=False), sa.Column("alias", sa.String(240), nullable=False), sa.ForeignKeyConstraint(["topic_id"], ["knowledge_topics.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("topic_id", "language", "alias"))
    op.create_index("ix_knowledge_topic_aliases_topic_id", "knowledge_topic_aliases", ["topic_id"])
    op.create_table("knowledge_cross_references",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False), sa.Column("source_entity_id", sa.Uuid(), nullable=False), sa.Column("target_type", sa.String(32), nullable=False), sa.Column("target_entity_id", sa.Uuid(), nullable=False), sa.Column("relationship_type", sa.String(40), nullable=False), sa.Column("rationale", sa.Text(), nullable=False), sa.Column("evidence_passage_id", sa.Uuid(), nullable=False), sa.Column("editorial_confidence", sa.Integer(), server_default="100", nullable=False), sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True), sa.Column("review_status", sa.String(24), server_default="pending", nullable=False), sa.Column("published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint("source_type IN ('quran_ayah','hadith_narration','tafsir_entry','topic')", name="ck_knowledge_cross_refs_source_type"), sa.CheckConstraint("target_type IN ('quran_ayah','hadith_narration','tafsir_entry','topic')", name="ck_knowledge_cross_refs_target_type"), sa.CheckConstraint("relationship_type IN ('explains','supports','contextualises','parallel','topic_membership','linguistic_note','historical_context','asbab_al_nuzul','editorial_link')", name="ck_knowledge_cross_refs_relationship"), sa.CheckConstraint("editorial_confidence BETWEEN 0 AND 100", name="ck_knowledge_cross_refs_confidence"), sa.CheckConstraint("NOT (source_type = target_type AND source_entity_id = target_entity_id)", name="ck_knowledge_cross_refs_not_self"), sa.ForeignKeyConstraint(["evidence_passage_id"], ["source_passages.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("source_type", "source_entity_id", "target_type", "target_entity_id", "relationship_type", "evidence_passage_id"))
    op.create_index("ix_knowledge_cross_refs_source", "knowledge_cross_references", ["source_type", "source_entity_id"])
    op.create_index("ix_knowledge_cross_refs_target", "knowledge_cross_references", ["target_type", "target_entity_id"])


def downgrade():
    op.drop_index("ix_knowledge_cross_refs_target", table_name="knowledge_cross_references")
    op.drop_index("ix_knowledge_cross_refs_source", table_name="knowledge_cross_references")
    op.drop_table("knowledge_cross_references")
    op.drop_index("ix_knowledge_topic_aliases_topic_id", table_name="knowledge_topic_aliases")
    op.drop_table("knowledge_topic_aliases")
    op.drop_index("ix_knowledge_topics_parent_topic_id", table_name="knowledge_topics")
    op.drop_table("knowledge_topics")
