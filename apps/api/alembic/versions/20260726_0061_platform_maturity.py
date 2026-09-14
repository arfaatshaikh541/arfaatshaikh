"""Milestone 15 platform maturity acceptance
Revision ID: 20260726_0061
Revises: 20260726_0060
"""
from alembic import op
import sqlalchemy as sa
revision='20260726_0061'; down_revision='20260726_0060'; branch_labels=None; depends_on=None
def upgrade():
 op.create_table('platform_maturity_reviews',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('milestone_version',sa.String(40),nullable=False),sa.Column('outcome',sa.String(16),nullable=False),sa.Column('portable_ready',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('production_ready',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('evidence_sha256',sa.String(64),nullable=False),sa.Column('notes',sa.Text()),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.UniqueConstraint('organisation_id','milestone_version',name='uq_platform_maturity_review_version'))
def downgrade():op.drop_table('platform_maturity_reviews')
