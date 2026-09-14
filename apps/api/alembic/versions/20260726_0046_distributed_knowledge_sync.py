"""distributed knowledge synchronization

Revision ID: 20260726_0046
Revises: 20260725_0045
"""
from alembic import op
import sqlalchemy as sa

revision = "20260726_0046"
down_revision = "20260725_0045"
branch_labels = None
depends_on = None


def _timestamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())]


def upgrade():
    op.create_table("knowledge_sync_nodes", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("organisation_id", sa.Uuid(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False), sa.Column("slug", sa.String(100), nullable=False), sa.Column("display_name", sa.String(180), nullable=False), sa.Column("base_url", sa.String(500), nullable=False), sa.Column("public_key_fingerprint", sa.String(64), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="pending"), sa.Column("trust_level", sa.String(16), nullable=False, server_default="restricted"), sa.Column("allowed_domains", sa.JSON(), nullable=False, server_default="[]"), *_timestamps(), sa.CheckConstraint("status IN ('pending','trusted','suspended','revoked')", name="ck_knowledge_sync_node_status"), sa.CheckConstraint("trust_level IN ('restricted','standard','high')", name="ck_knowledge_sync_node_trust_level"), sa.UniqueConstraint("organisation_id", "slug", name="uq_knowledge_sync_node_org_slug"))
    op.create_table("knowledge_sync_trust_policies", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("organisation_id", sa.Uuid(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False), sa.Column("node_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_nodes.id", ondelete="CASCADE"), nullable=False), sa.Column("direction", sa.String(16), nullable=False, server_default="pull"), sa.Column("allowed_content_types", sa.JSON(), nullable=False, server_default="[]"), sa.Column("require_signature", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("require_scholarly_approval", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("max_items_per_run", sa.Integer(), nullable=False, server_default="1000"), *_timestamps(), sa.CheckConstraint("direction IN ('pull','push','bidirectional')", name="ck_knowledge_sync_policy_direction"), sa.UniqueConstraint("organisation_id", "node_id", name="uq_knowledge_sync_policy_org_node"))
    op.create_table("knowledge_sync_runs", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("organisation_id", sa.Uuid(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False), sa.Column("node_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_nodes.id", ondelete="RESTRICT"), nullable=False), sa.Column("direction", sa.String(8), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="planned"), sa.Column("request_id", sa.String(100), nullable=False, unique=True), sa.Column("manifest_sha256", sa.String(64), nullable=False), sa.Column("source_checkpoint", sa.String(200), nullable=True), sa.Column("next_checkpoint", sa.String(200), nullable=True), sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("accepted_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"), *_timestamps(), sa.CheckConstraint("status IN ('planned','running','completed','partial','failed','cancelled')", name="ck_knowledge_sync_run_status"), sa.CheckConstraint("direction IN ('pull','push')", name="ck_knowledge_sync_run_direction"))
    op.create_index("ix_knowledge_sync_run_node_status", "knowledge_sync_runs", ["node_id", "status"])
    op.create_table("knowledge_sync_items", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("run_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_runs.id", ondelete="CASCADE"), nullable=False), sa.Column("external_id", sa.String(200), nullable=False), sa.Column("content_type", sa.String(40), nullable=False), sa.Column("content_version", sa.String(80), nullable=False), sa.Column("payload_sha256", sa.String(64), nullable=False), sa.Column("signature", sa.Text(), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="pending"), sa.Column("reason_codes", sa.JSON(), nullable=False, server_default="[]"), *_timestamps(), sa.CheckConstraint("status IN ('pending','accepted','rejected','conflict')", name="ck_knowledge_sync_item_status"), sa.UniqueConstraint("run_id", "external_id", "content_version", name="uq_knowledge_sync_item_run_external_version"))
    op.create_index("ix_knowledge_sync_item_run_status", "knowledge_sync_items", ["run_id", "status"])
    op.create_table("knowledge_sync_conflicts", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("run_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_runs.id", ondelete="CASCADE"), nullable=False), sa.Column("external_id", sa.String(200), nullable=False), sa.Column("local_version", sa.String(80), nullable=False), sa.Column("remote_version", sa.String(80), nullable=False), sa.Column("local_sha256", sa.String(64), nullable=False), sa.Column("remote_sha256", sa.String(64), nullable=False), sa.Column("resolution", sa.String(20), nullable=False, server_default="pending"), sa.Column("resolution_evidence_sha256", sa.String(64), nullable=True), *_timestamps(), sa.CheckConstraint("resolution IN ('pending','keep_local','accept_remote','manual_merge','reject_remote')", name="ck_knowledge_sync_conflict_resolution"), sa.UniqueConstraint("run_id", "external_id", name="uq_knowledge_sync_conflict_run_external"))
    op.create_table("knowledge_sync_audit_events", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("run_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_runs.id", ondelete="CASCADE"), nullable=False), sa.Column("sequence_number", sa.Integer(), nullable=False), sa.Column("event_type", sa.String(50), nullable=False), sa.Column("evidence_sha256", sa.String(64), nullable=False), sa.Column("previous_event_sha256", sa.String(64), nullable=True), sa.Column("event_sha256", sa.String(64), nullable=False), sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"), *_timestamps(), sa.UniqueConstraint("run_id", "sequence_number", name="uq_knowledge_sync_audit_run_sequence"))
    op.create_index("ix_knowledge_sync_audit_run", "knowledge_sync_audit_events", ["run_id"])


def downgrade():
    op.drop_table("knowledge_sync_audit_events")
    op.drop_table("knowledge_sync_conflicts")
    op.drop_table("knowledge_sync_items")
    op.drop_table("knowledge_sync_runs")
    op.drop_table("knowledge_sync_trust_policies")
    op.drop_table("knowledge_sync_nodes")
