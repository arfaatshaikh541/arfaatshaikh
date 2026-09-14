"""registry hardening and audit exports

Revision ID: 20260725_0008
Revises: 20260725_0007
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260725_0008"
down_revision = "20260725_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_audit_exports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("edition_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("format", sa.String(length=12), nullable=False),
        sa.Column("filters_json", sa.Text(), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("format IN ('json','csv')", name="ck_source_audit_exports_format"),
        sa.ForeignKeyConstraint(["edition_id"], ["source_editions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_audit_exports_created", "source_audit_exports", ["created_at"])
    op.create_index(op.f("ix_source_audit_exports_edition_id"), "source_audit_exports", ["edition_id"])
    op.create_index(op.f("ix_source_audit_exports_requested_by_user_id"), "source_audit_exports", ["requested_by_user_id"])
    op.execute("""
    CREATE OR REPLACE FUNCTION prevent_source_audit_export_mutation() RETURNS trigger AS $$
    BEGIN
      RAISE EXCEPTION 'source audit export records are append-only';
    END;
    $$ LANGUAGE plpgsql
    """)
    op.execute("""
    CREATE TRIGGER trg_source_audit_exports_immutable
    BEFORE UPDATE OR DELETE ON source_audit_exports
    FOR EACH ROW EXECUTE FUNCTION prevent_source_audit_export_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_source_audit_exports_immutable ON source_audit_exports")
    op.execute("DROP FUNCTION IF EXISTS prevent_source_audit_export_mutation()")
    op.drop_index(op.f("ix_source_audit_exports_requested_by_user_id"), table_name="source_audit_exports")
    op.drop_index(op.f("ix_source_audit_exports_edition_id"), table_name="source_audit_exports")
    op.drop_index("ix_source_audit_exports_created", table_name="source_audit_exports")
    op.drop_table("source_audit_exports")
