"""add controlled source lifecycle and provenance passages

Revision ID: 20260725_0006
Revises: 20260725_0005
Create Date: 2026-07-25
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260725_0006"
down_revision: str | None = "20260725_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "source_review_assignments",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("review_domain", sa.String(60), nullable=False),
        sa.Column("status", sa.String(24), server_default="assigned", nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["edition_id"], ["source_editions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("edition_id", "reviewer_user_id", "review_domain", "status"),
        sa.CheckConstraint("status IN ('assigned','in_progress','completed','cancelled')", name="ck_source_review_assignments_status"),
    )
    op.create_index("ix_source_review_assignments_edition_id", "source_review_assignments", ["edition_id"])
    op.create_index("ix_source_review_assignments_reviewer_user_id", "source_review_assignments", ["reviewer_user_id"])
    op.create_index("ix_source_review_assignments_reviewer_status", "source_review_assignments", ["reviewer_user_id", "status"])

    op.create_table(
        "source_passages",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("passage_key", sa.String(240), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("source_locator", sa.String(500), nullable=False),
        sa.Column("citation_label", sa.String(500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["edition_id"], ["source_editions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("edition_id", "passage_key", "version"),
        sa.CheckConstraint("version > 0", name="ck_source_passages_version_positive"),
    )
    op.create_index("ix_source_passages_edition_id", "source_passages", ["edition_id"])
    op.create_index("ix_source_passages_edition_key", "source_passages", ["edition_id", "passage_key"])

    op.create_table(
        "source_attributions",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("display_text", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(500)),
        sa.Column("licence_url", sa.String(500)),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["edition_id"], ["source_editions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("edition_id", "language"),
    )
    op.create_index("ix_source_attributions_edition_id", "source_attributions", ["edition_id"])

    op.create_table(
        "source_lifecycle_events",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("from_status", sa.String(40)),
        sa.Column("to_status", sa.String(40)),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["edition_id"], ["source_editions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_source_lifecycle_events_edition_id", "source_lifecycle_events", ["edition_id"])
    op.create_index("ix_source_lifecycle_edition_created", "source_lifecycle_events", ["edition_id", "created_at"])

    op.execute(
        "CREATE TRIGGER trg_source_lifecycle_events_append_only BEFORE UPDATE OR DELETE ON source_lifecycle_events "
        "FOR EACH ROW EXECUTE FUNCTION prevent_event_mutation()"
    )
    op.execute(
        "CREATE OR REPLACE FUNCTION protect_source_passage_content() RETURNS trigger AS $$ "
        "BEGIN IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'source passages are immutable'; END IF; "
        "IF NEW.edition_id IS DISTINCT FROM OLD.edition_id OR NEW.passage_key IS DISTINCT FROM OLD.passage_key "
        "OR NEW.version IS DISTINCT FROM OLD.version OR NEW.language IS DISTINCT FROM OLD.language "
        "OR NEW.source_locator IS DISTINCT FROM OLD.source_locator OR NEW.citation_label IS DISTINCT FROM OLD.citation_label "
        "OR NEW.content IS DISTINCT FROM OLD.content OR NEW.content_sha256 IS DISTINCT FROM OLD.content_sha256 "
        "OR NEW.created_by_user_id IS DISTINCT FROM OLD.created_by_user_id THEN "
        "RAISE EXCEPTION 'source passage content is immutable'; END IF; RETURN NEW; END; $$ LANGUAGE plpgsql"
    )
    op.execute(
        "CREATE TRIGGER trg_source_passages_content_immutable BEFORE UPDATE OR DELETE ON source_passages "
        "FOR EACH ROW EXECUTE FUNCTION protect_source_passage_content()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_source_lifecycle_events_append_only ON source_lifecycle_events")
    op.execute("DROP TRIGGER IF EXISTS trg_source_passages_content_immutable ON source_passages")
    op.execute("DROP FUNCTION IF EXISTS protect_source_passage_content()")
    op.drop_table("source_lifecycle_events")
    op.drop_table("source_attributions")
    op.drop_table("source_passages")
    op.drop_table("source_review_assignments")
