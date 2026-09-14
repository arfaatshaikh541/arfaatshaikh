"""synchronization transport orchestration

Revision ID: 20260726_0047
Revises: 20260726_0046
"""
from alembic import op
import sqlalchemy as sa

revision = "20260726_0047"
down_revision = "20260726_0046"
branch_labels = None
depends_on = None


def _timestamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())]


def upgrade():
    op.create_table("knowledge_sync_schedules", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("organisation_id", sa.Uuid(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False), sa.Column("node_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_nodes.id", ondelete="CASCADE"), nullable=False), sa.Column("direction", sa.String(8), nullable=False), sa.Column("status", sa.String(12), nullable=False, server_default="active"), sa.Column("interval_minutes", sa.Integer(), nullable=False, server_default="60"), sa.Column("max_concurrent_runs", sa.Integer(), nullable=False, server_default="1"), sa.Column("jitter_seconds", sa.Integer(), nullable=False, server_default="30"), *_timestamps(), sa.CheckConstraint("status IN ('active','paused','disabled')", name="ck_knowledge_sync_schedule_status"), sa.CheckConstraint("direction IN ('pull','push')", name="ck_knowledge_sync_schedule_direction"), sa.UniqueConstraint("organisation_id", "node_id", "direction", name="uq_knowledge_sync_schedule_org_node_direction"))
    op.create_table("knowledge_sync_transfer_batches", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("run_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_runs.id", ondelete="CASCADE"), nullable=False), sa.Column("batch_number", sa.Integer(), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="planned"), sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("byte_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("completed_chunks", sa.Integer(), nullable=False, server_default="0"), sa.Column("failed_chunks", sa.Integer(), nullable=False, server_default="0"), *_timestamps(), sa.CheckConstraint("status IN ('planned','transferring','completed','partial','failed','cancelled')", name="ck_knowledge_sync_transfer_batch_status"), sa.UniqueConstraint("run_id", "batch_number", name="uq_knowledge_sync_transfer_batch_run_number"))
    op.create_index("ix_knowledge_sync_transfer_batch_run_status", "knowledge_sync_transfer_batches", ["run_id", "status"])
    op.create_table("knowledge_sync_transfer_chunks", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("batch_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_transfer_batches.id", ondelete="CASCADE"), nullable=False), sa.Column("chunk_number", sa.Integer(), nullable=False), sa.Column("idempotency_key", sa.String(120), nullable=False), sa.Column("payload_sha256", sa.String(64), nullable=False), sa.Column("compressed_sha256", sa.String(64), nullable=True), sa.Column("byte_count", sa.Integer(), nullable=False), sa.Column("item_count", sa.Integer(), nullable=False), sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("status", sa.String(16), nullable=False, server_default="pending"), *_timestamps(), sa.CheckConstraint("status IN ('pending','transferring','verified','failed','dead_lettered','cancelled')", name="ck_knowledge_sync_transfer_chunk_status"), sa.UniqueConstraint("batch_id", "chunk_number", name="uq_knowledge_sync_transfer_chunk_batch_number"), sa.UniqueConstraint("batch_id", "idempotency_key", name="uq_knowledge_sync_transfer_chunk_batch_idempotency"))
    op.create_index("ix_knowledge_sync_transfer_chunk_batch_status", "knowledge_sync_transfer_chunks", ["batch_id", "status"])
    op.create_table("knowledge_sync_transfer_attempts", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("chunk_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_transfer_chunks.id", ondelete="CASCADE"), nullable=False), sa.Column("attempt_number", sa.Integer(), nullable=False), sa.Column("outcome", sa.String(20), nullable=False), sa.Column("response_status", sa.Integer(), nullable=True), sa.Column("error_code", sa.String(80), nullable=True), sa.Column("evidence_sha256", sa.String(64), nullable=False), sa.Column("retry_after_seconds", sa.Integer(), nullable=True), *_timestamps(), sa.CheckConstraint("outcome IN ('success','retry','permanent_failure','cancelled')", name="ck_knowledge_sync_transfer_attempt_outcome"), sa.UniqueConstraint("chunk_id", "attempt_number", name="uq_knowledge_sync_transfer_attempt_chunk_number"))
    op.create_table("knowledge_sync_dead_letters", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("chunk_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_transfer_chunks.id", ondelete="CASCADE"), nullable=False), sa.Column("status", sa.String(12), nullable=False, server_default="open"), sa.Column("reason_code", sa.String(80), nullable=False), sa.Column("evidence_sha256", sa.String(64), nullable=False), sa.Column("resolution_notes", sa.Text(), nullable=True), sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"), *_timestamps(), sa.CheckConstraint("status IN ('open','requeued','resolved','discarded')", name="ck_knowledge_sync_dead_letter_status"), sa.UniqueConstraint("chunk_id", name="uq_knowledge_sync_dead_letter_chunk"))


def downgrade():
    op.drop_table("knowledge_sync_dead_letters")
    op.drop_table("knowledge_sync_transfer_attempts")
    op.drop_table("knowledge_sync_transfer_chunks")
    op.drop_table("knowledge_sync_transfer_batches")
    op.drop_table("knowledge_sync_schedules")
