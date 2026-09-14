"""Milestone 13

Revision ID: 20260726_0053
Revises: 20260726_0052
"""
from alembic import op
import sqlalchemy as sa

def _ts(): return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())]

revision="20260726_0053"
down_revision="20260726_0052"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("regional_rollout_reviews", sa.Column("id",sa.Uuid(),primary_key=True), sa.Column("organisation_id",sa.Uuid(),sa.ForeignKey("organisations.id",ondelete="CASCADE"),nullable=False), sa.Column("region",sa.String(20),nullable=False), sa.Column("review_version",sa.String(40),nullable=False), sa.Column("outcome",sa.String(16),nullable=False,server_default="pending"), sa.Column("portable_ready",sa.Boolean(),nullable=False,server_default=sa.false()), sa.Column("production_ready",sa.Boolean(),nullable=False,server_default=sa.false()), sa.Column("evidence_sha256",sa.String(64),nullable=False), *_ts(), sa.CheckConstraint("outcome IN ('pending','passed','failed','conditional')",name="ck_regional_rollout_review_outcome"), sa.UniqueConstraint("organisation_id","region","review_version",name="uq_regional_rollout_review_version"))
    op.create_table("global_launch_reviews", sa.Column("id",sa.Uuid(),primary_key=True), sa.Column("organisation_id",sa.Uuid(),sa.ForeignKey("organisations.id",ondelete="CASCADE"),nullable=False), sa.Column("review_version",sa.String(40),nullable=False), sa.Column("outcome",sa.String(16),nullable=False,server_default="pending"), sa.Column("portable_ready",sa.Boolean(),nullable=False,server_default=sa.false()), sa.Column("production_ready",sa.Boolean(),nullable=False,server_default=sa.false()), sa.Column("evidence_sha256",sa.String(64),nullable=False), sa.Column("controls_json",sa.JSON(),nullable=False,server_default="{}"), *_ts(), sa.CheckConstraint("outcome IN ('pending','passed','failed','conditional')",name="ck_global_launch_review_outcome"), sa.UniqueConstraint("organisation_id","review_version",name="uq_global_launch_review_version"))
    op.create_table("institutional_network_acceptances", sa.Column("id",sa.Uuid(),primary_key=True), sa.Column("organisation_id",sa.Uuid(),sa.ForeignKey("organisations.id",ondelete="CASCADE"),nullable=False), sa.Column("milestone_version",sa.String(40),nullable=False), sa.Column("outcome",sa.String(16),nullable=False), sa.Column("portable_acceptance",sa.Boolean(),nullable=False,server_default=sa.false()), sa.Column("production_acceptance",sa.Boolean(),nullable=False,server_default=sa.false()), sa.Column("evidence_sha256",sa.String(64),nullable=False), sa.Column("notes",sa.Text()), *_ts(), sa.UniqueConstraint("organisation_id","milestone_version",name="uq_institutional_network_acceptance_version"))
def downgrade():
    op.drop_table("institutional_network_acceptances"); op.drop_table("global_launch_reviews"); op.drop_table("regional_rollout_reviews")
