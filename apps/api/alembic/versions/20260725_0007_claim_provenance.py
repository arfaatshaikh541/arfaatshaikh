"""add claim provenance corrections supersession and approval policies

Revision ID: 20260725_0007
Revises: 20260725_0006
Create Date: 2026-07-25
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20260725_0007"
down_revision: str | None = "20260725_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_claims",
        sa.Column("claim_text", sa.Text(), nullable=False), sa.Column("language", sa.String(16), nullable=False),
        sa.Column("claim_status", sa.String(24), server_default="draft", nullable=False),
        sa.Column("methodology", sa.String(120)), sa.Column("dispute_notes", sa.Text()),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False), sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"), sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("claim_status IN ('draft','reviewed','approved','disputed','withdrawn')", name="ck_source_claims_status"),
    )
    op.create_index("ix_source_claims_status_created", "source_claims", ["claim_status", "created_at"])

    op.create_table(
        "claim_passage_links",
        sa.Column("claim_id", sa.Uuid(), nullable=False), sa.Column("passage_id", sa.Uuid(), nullable=False),
        sa.Column("relation_type", sa.String(32), nullable=False), sa.Column("citation_start", sa.Integer(), nullable=False),
        sa.Column("citation_end", sa.Integer(), nullable=False), sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False), sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["claim_id"], ["source_claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["passage_id"], ["source_passages.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("claim_id", "passage_id", "relation_type"),
        sa.CheckConstraint("relation_type IN ('supports','qualifies','disputes','contextualises')", name="ck_claim_passage_links_relation"),
        sa.CheckConstraint("citation_start >= 0 AND citation_end > citation_start", name="ck_claim_passage_links_span"),
    )
    op.create_index("ix_claim_passage_links_claim_id", "claim_passage_links", ["claim_id"])
    op.create_index("ix_claim_passage_links_passage_id", "claim_passage_links", ["passage_id"])

    op.create_table(
        "passage_corrections",
        sa.Column("passage_id", sa.Uuid(), nullable=False), sa.Column("replacement_passage_id", sa.Uuid()),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False), sa.Column("decided_by_user_id", sa.Uuid()),
        sa.Column("reason", sa.Text(), nullable=False), sa.Column("status", sa.String(24), server_default="requested", nullable=False),
        sa.Column("decision_notes", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True)), sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["passage_id"], ["source_passages.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["replacement_passage_id"], ["source_passages.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('requested','accepted','rejected','superseded')", name="ck_passage_corrections_status"),
    )
    op.create_index("ix_passage_corrections_passage_created", "passage_corrections", ["passage_id", "created_at"])

    op.create_table(
        "source_supersessions",
        sa.Column("superseded_edition_id", sa.Uuid(), nullable=False), sa.Column("replacement_edition_id", sa.Uuid(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False), sa.Column("recorded_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["superseded_edition_id"], ["source_editions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["replacement_edition_id"], ["source_editions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("superseded_edition_id", "replacement_edition_id"),
        sa.CheckConstraint("superseded_edition_id <> replacement_edition_id", name="ck_source_supersessions_distinct"),
    )
    op.create_index("ix_source_supersessions_superseded_edition_id", "source_supersessions", ["superseded_edition_id"])
    op.create_index("ix_source_supersessions_replacement_edition_id", "source_supersessions", ["replacement_edition_id"])

    op.create_table(
        "approval_policies",
        sa.Column("source_type", sa.String(40), nullable=False), sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), server_default="draft", nullable=False),
        sa.Column("minimum_reviewers", sa.Integer(), server_default="1", nullable=False),
        sa.Column("require_legal_approval", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("require_integrity_verification", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("required_review_domains", sa.Text(), nullable=False), sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"), sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("source_type", "policy_version"),
        sa.CheckConstraint("status IN ('draft','active','retired')", name="ck_approval_policies_status"),
    )

    for table in ("claim_passage_links", "passage_corrections", "source_supersessions"):
        op.execute(f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION prevent_event_mutation()")


def downgrade() -> None:
    for table in ("source_supersessions", "passage_corrections", "claim_passage_links"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    op.drop_table("approval_policies")
    op.drop_table("source_supersessions")
    op.drop_table("passage_corrections")
    op.drop_table("claim_passage_links")
    op.drop_table("source_claims")
