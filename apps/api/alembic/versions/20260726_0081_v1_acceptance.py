"""Milestone 20 v1 acceptance
Revision ID: 20260726_0081
Revises: 20260726_0080
"""
from alembic import op
import sqlalchemy as sa
revision='20260726_0081';down_revision='20260726_0080';branch_labels=None;depends_on=None
def _ts():return [sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]
def upgrade():
 op.create_table('release_governance_decisions',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('release_id',sa.Uuid(),sa.ForeignKey('release_candidates.id',ondelete='CASCADE'),nullable=False),sa.Column('decision',sa.String(20),nullable=False),sa.Column('owner_reference',sa.String(180),nullable=False),sa.Column('rollback_authority_reference',sa.String(180),nullable=False),sa.Column('evidence_sha256',sa.String(64),nullable=False),*_ts())
 op.create_table('production_validation_records',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('release_id',sa.Uuid(),sa.ForeignKey('release_candidates.id',ondelete='CASCADE'),nullable=False),sa.Column('validation_type',sa.String(80),nullable=False),sa.Column('passed',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('external_party',sa.String(180)),sa.Column('evidence_sha256',sa.String(64),nullable=False),*_ts())
 op.create_table('platform_v1_acceptance',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('release_version',sa.String(40),nullable=False),sa.Column('outcome',sa.String(20),nullable=False),sa.Column('portable_ready',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('production_ready',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('evidence_sha256',sa.String(64),nullable=False),sa.Column('notes',sa.Text()),*_ts(),sa.UniqueConstraint('organisation_id','release_version',name='uq_platform_v1_acceptance'))
def downgrade():
 op.drop_table('platform_v1_acceptance');op.drop_table('production_validation_records');op.drop_table('release_governance_decisions')
