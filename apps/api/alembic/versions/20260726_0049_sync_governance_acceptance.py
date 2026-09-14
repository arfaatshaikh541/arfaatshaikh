"""synchronization governance and acceptance

Revision ID: 20260726_0049
Revises: 20260726_0048
"""
from alembic import op
import sqlalchemy as sa

revision = "20260726_0049"
down_revision = "20260726_0048"
branch_labels = None
depends_on = None


def _timestamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())]


def upgrade():
    op.create_table("knowledge_sync_peer_attestations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organisation_id", sa.Uuid(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attestation_version", sa.String(40), nullable=False),
        sa.Column("evidence_sha256", sa.String(64), nullable=False),
        sa.Column("independent_reviewer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("expires_in_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"), *_timestamps(),
        sa.CheckConstraint("status IN ('pending','active','expired','revoked')", name="ck_knowledge_sync_peer_attestation_status"),
        sa.UniqueConstraint("node_id", "attestation_version", name="uq_knowledge_sync_peer_attestation_node_version"))
    op.create_index("ix_knowledge_sync_peer_attestation_node_status", "knowledge_sync_peer_attestations", ["node_id", "status"])

    op.create_table("knowledge_sync_policy_changes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("trust_policy_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_trust_policies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("change_ticket", sa.String(120), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("before_policy_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("after_policy_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("evidence_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="proposed"), *_timestamps(),
        sa.CheckConstraint("status IN ('proposed','approved','rejected','applied','rolled_back')", name="ck_knowledge_sync_policy_change_status"),
        sa.CheckConstraint("risk_level IN ('low','medium','high','critical')", name="ck_knowledge_sync_policy_change_risk"))
    op.create_index("ix_knowledge_sync_policy_change_policy_status", "knowledge_sync_policy_changes", ["trust_policy_id", "status"])

    op.create_table("knowledge_sync_security_incidents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organisation_id", sa.Uuid(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("evidence_sha256", sa.String(64), nullable=False),
        sa.Column("node_suspended", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("credentials_revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("transfers_cancelled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("summary", sa.Text(), nullable=False), *_timestamps(),
        sa.CheckConstraint("severity IN ('low','medium','high','critical')", name="ck_knowledge_sync_security_incident_severity"),
        sa.CheckConstraint("status IN ('open','contained','resolved','dismissed')", name="ck_knowledge_sync_security_incident_status"))
    op.create_index("ix_knowledge_sync_security_incident_node_status", "knowledge_sync_security_incidents", ["node_id", "status"])

    op.create_table("knowledge_sync_quarantines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("incident_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_security_incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.Uuid(), sa.ForeignKey("knowledge_sync_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("release_evidence_sha256", sa.String(64), nullable=True),
        sa.Column("integrity_verification_passed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("credentials_rotated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("independent_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True), *_timestamps(),
        sa.CheckConstraint("status IN ('active','release_pending','released','expired')", name="ck_knowledge_sync_quarantine_status"),
        sa.UniqueConstraint("incident_id", name="uq_knowledge_sync_quarantine_incident"))

    op.create_table("knowledge_sync_acceptance_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organisation_id", sa.Uuid(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("review_version", sa.String(40), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("open_high_incidents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("open_critical_incidents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evidence_sha256", sa.String(64), nullable=False),
        sa.Column("controls_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=True), *_timestamps(),
        sa.CheckConstraint("outcome IN ('pending','passed','failed','conditional')", name="ck_knowledge_sync_acceptance_review_outcome"),
        sa.UniqueConstraint("organisation_id", "review_version", name="uq_knowledge_sync_acceptance_org_version"))


def downgrade():
    op.drop_table("knowledge_sync_acceptance_reviews")
    op.drop_table("knowledge_sync_quarantines")
    op.drop_index("ix_knowledge_sync_security_incident_node_status", table_name="knowledge_sync_security_incidents")
    op.drop_table("knowledge_sync_security_incidents")
    op.drop_index("ix_knowledge_sync_policy_change_policy_status", table_name="knowledge_sync_policy_changes")
    op.drop_table("knowledge_sync_policy_changes")
    op.drop_index("ix_knowledge_sync_peer_attestation_node_status", table_name="knowledge_sync_peer_attestations")
    op.drop_table("knowledge_sync_peer_attestations")
