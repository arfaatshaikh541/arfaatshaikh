"""synchronization integrity and reconciliation

Revision ID: 20260726_0048
Revises: 20260726_0047
"""
from alembic import op
import sqlalchemy as sa

revision = "20260726_0048"
down_revision = "20260726_0047"
branch_labels = None
depends_on = None


def _timestamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())]


def upgrade():
    op.create_table("knowledge_sync_snapshots", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("organisation_id", sa.Uuid(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False), sa.Column("node_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_nodes.id", ondelete="CASCADE"), nullable=False), sa.Column("content_type", sa.String(32), nullable=False), sa.Column("snapshot_version", sa.String(80), nullable=False), sa.Column("root_sha256", sa.String(64), nullable=False), sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("partition_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("status", sa.String(16), nullable=False, server_default="building"), *_timestamps(), sa.CheckConstraint("status IN ('building','sealed','verified','invalidated')", name="ck_knowledge_sync_snapshot_status"), sa.UniqueConstraint("node_id", "content_type", "snapshot_version", name="uq_knowledge_sync_snapshot_node_type_version"))
    op.create_index("ix_knowledge_sync_snapshot_node_status", "knowledge_sync_snapshots", ["node_id", "status"])
    op.create_table("knowledge_sync_partition_digests", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_snapshots.id", ondelete="CASCADE"), nullable=False), sa.Column("partition_key", sa.String(160), nullable=False), sa.Column("first_canonical_id", sa.String(240), nullable=False), sa.Column("last_canonical_id", sa.String(240), nullable=False), sa.Column("item_count", sa.Integer(), nullable=False), sa.Column("digest_sha256", sa.String(64), nullable=False), *_timestamps(), sa.UniqueConstraint("snapshot_id", "partition_key", name="uq_knowledge_sync_partition_snapshot_key"))
    op.create_index("ix_knowledge_sync_partition_snapshot", "knowledge_sync_partition_digests", ["snapshot_id"])
    op.create_table("knowledge_sync_drift_reports", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("local_snapshot_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_snapshots.id", ondelete="CASCADE"), nullable=False), sa.Column("remote_snapshot_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_snapshots.id", ondelete="CASCADE"), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="clean"), sa.Column("matching_partitions", sa.Integer(), nullable=False, server_default="0"), sa.Column("divergent_partitions", sa.Integer(), nullable=False, server_default="0"), sa.Column("missing_local_partitions", sa.Integer(), nullable=False, server_default="0"), sa.Column("missing_remote_partitions", sa.Integer(), nullable=False, server_default="0"), sa.Column("evidence_sha256", sa.String(64), nullable=False), *_timestamps(), sa.CheckConstraint("status IN ('clean','drift_detected','repair_planned','resolved','dismissed')", name="ck_knowledge_sync_drift_status"), sa.UniqueConstraint("local_snapshot_id", "remote_snapshot_id", name="uq_knowledge_sync_drift_snapshot_pair"))
    op.create_table("knowledge_sync_repair_plans", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("drift_report_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_drift_reports.id", ondelete="CASCADE"), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="draft"), sa.Column("strategy", sa.String(24), nullable=False), sa.Column("partition_keys_json", sa.JSON(), nullable=False, server_default="[]"), sa.Column("requires_scholarly_review", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("approved_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True), sa.Column("notes", sa.Text(), nullable=True), *_timestamps(), sa.CheckConstraint("status IN ('draft','approved','executing','completed','failed','cancelled')", name="ck_knowledge_sync_repair_plan_status"), sa.CheckConstraint("strategy IN ('fetch_missing','replace_divergent','manual_review')", name="ck_knowledge_sync_repair_strategy"))
    op.create_table("knowledge_sync_integrity_verifications", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_snapshots.id", ondelete="CASCADE"), nullable=False), sa.Column("verification_version", sa.String(40), nullable=False), sa.Column("outcome", sa.String(16), nullable=False), sa.Column("calculated_root_sha256", sa.String(64), nullable=False), sa.Column("expected_root_sha256", sa.String(64), nullable=False), sa.Column("evidence_sha256", sa.String(64), nullable=False), sa.Column("verified_partitions", sa.Integer(), nullable=False, server_default="0"), *_timestamps(), sa.CheckConstraint("outcome IN ('passed','failed','inconclusive')", name="ck_knowledge_sync_integrity_verification_outcome"), sa.UniqueConstraint("snapshot_id", "verification_version", name="uq_knowledge_sync_integrity_snapshot_version"))


def downgrade():
    op.drop_table("knowledge_sync_integrity_verifications")
    op.drop_table("knowledge_sync_repair_plans")
    op.drop_table("knowledge_sync_drift_reports")
    op.drop_table("knowledge_sync_partition_digests")
    op.drop_table("knowledge_sync_snapshots")
