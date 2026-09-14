"""add Islamic source registry and provenance metadata

Revision ID: 20260725_0005
Revises: 20260725_0004
Create Date: 2026-07-25
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260725_0005"
down_revision: str | None = "20260725_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def base_columns():
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "source_licences",
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("spdx_identifier", sa.String(80)), sa.Column("version", sa.String(40)),
        sa.Column("licence_url", sa.String(500)), sa.Column("copyright_holder", sa.String(240)),
        sa.Column("redistribution_allowed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("modification_allowed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("commercial_use_allowed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("attribution_text", sa.Text()), sa.Column("restrictions", sa.Text()),
        sa.Column("legal_review_status", sa.String(24), server_default="pending", nullable=False),
        *base_columns(), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("spdx_identifier", "version"),
    )
    op.create_table(
        "sources",
        sa.Column("canonical_title", sa.String(500), nullable=False), sa.Column("original_title", sa.String(500)),
        sa.Column("source_type", sa.String(40), nullable=False), sa.Column("primary_language", sa.String(16), nullable=False),
        sa.Column("author_name", sa.String(300)), sa.Column("compiler_name", sa.String(300)),
        sa.Column("description", sa.Text()), sa.Column("authority_status", sa.String(24), server_default="unassessed", nullable=False),
        sa.Column("public_notes", sa.Text()), *base_columns(), sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("source_type IN ('quran','hadith','tafsir','fiqh','aqidah','seerah','history','arabic','comparative_religion','modern_analysis','other')", name="ck_sources_type"),
        sa.CheckConstraint("authority_status IN ('unassessed','candidate','approved','restricted','rejected')", name="ck_sources_authority_status"),
    )
    op.create_index("ix_sources_type_status", "sources", ["source_type", "authority_status"])
    op.create_table(
        "source_editions",
        sa.Column("source_id", sa.Uuid(), nullable=False), sa.Column("licence_id", sa.Uuid()),
        sa.Column("edition_key", sa.String(120), nullable=False), sa.Column("edition_statement", sa.String(300)),
        sa.Column("publisher", sa.String(300)), sa.Column("publication_year", sa.Integer()),
        sa.Column("editor_name", sa.String(300)), sa.Column("translator_name", sa.String(300)),
        sa.Column("language", sa.String(16), nullable=False), sa.Column("isbn", sa.String(32)),
        sa.Column("citation_format", sa.Text(), nullable=False),
        sa.Column("ingestion_status", sa.String(24), server_default="not_started", nullable=False),
        sa.Column("review_status", sa.String(24), server_default="pending", nullable=False),
        sa.Column("approved_for_retrieval", sa.Boolean(), server_default="false", nullable=False),
        *base_columns(), sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["licence_id"], ["source_licences.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("source_id", "edition_key"),
        sa.CheckConstraint("ingestion_status IN ('not_started','registered','validating','ready','blocked','retired')", name="ck_source_editions_ingestion_status"),
        sa.CheckConstraint("review_status IN ('pending','in_review','approved','changes_requested','rejected','expired')", name="ck_source_editions_review_status"),
    )
    op.create_index("ix_source_editions_source_id", "source_editions", ["source_id"])
    op.create_index("ix_source_editions_licence_id", "source_editions", ["licence_id"])
    op.create_index("ix_source_editions_source_review", "source_editions", ["source_id", "review_status"])
    op.create_table(
        "source_acquisitions",
        sa.Column("edition_id", sa.Uuid(), nullable=False), sa.Column("method", sa.String(40), nullable=False),
        sa.Column("acquired_from", sa.String(500), nullable=False), sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_reference", sa.String(500)), sa.Column("terms_snapshot_object_key", sa.String(500)),
        sa.Column("recorded_by_user_id", sa.Uuid(), nullable=False), *base_columns(), sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["edition_id"], ["source_editions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("method IN ('publisher_delivery','licensed_api','institutional_archive','manual_upload','public_domain_import','other')", name="ck_source_acquisitions_method"),
    )
    op.create_index("ix_source_acquisitions_edition_id", "source_acquisitions", ["edition_id"])
    op.create_table(
        "source_integrity_records",
        sa.Column("edition_id", sa.Uuid(), nullable=False), sa.Column("object_key", sa.String(500), nullable=False),
        sa.Column("algorithm", sa.String(16), nullable=False), sa.Column("digest", sa.String(128), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False), sa.Column("verified", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)), sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["edition_id"], ["source_editions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("edition_id", "algorithm", "digest"),
        sa.CheckConstraint("algorithm IN ('sha256','sha512')", name="ck_source_integrity_algorithm"),
    )
    op.create_index("ix_source_integrity_edition_created", "source_integrity_records", ["edition_id", "created_at"])
    op.create_table(
        "source_reviews",
        sa.Column("edition_id", sa.Uuid(), nullable=False), sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("review_domain", sa.String(60), nullable=False), sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False), sa.Column("valid_until", sa.Date()),
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["edition_id"], ["source_editions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("decision IN ('pending','approved','changes_requested','rejected','expired')", name="ck_source_reviews_decision"),
    )
    op.create_index("ix_source_reviews_edition_created", "source_reviews", ["edition_id", "created_at"])

    for table in ("source_integrity_records", "source_reviews"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION prevent_event_mutation()"
        )


def downgrade() -> None:
    for table in ("source_reviews", "source_integrity_records"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    for table in ("source_reviews", "source_integrity_records", "source_acquisitions", "source_editions", "sources", "source_licences"):
        op.drop_table(table)
