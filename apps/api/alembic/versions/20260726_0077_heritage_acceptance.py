"""Milestone 19 heritage and acceptance
Revision ID: 20260726_0077
Revises: 20260726_0076
"""
from alembic import op
import sqlalchemy as sa
revision='20260726_0077';down_revision='20260726_0076';branch_labels=None;depends_on=None
def _ts():return [sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]
def upgrade():
 op.create_table('heritage_site_records',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('site_slug',sa.String(120),nullable=False),sa.Column('jurisdiction_code',sa.String(8),nullable=False),sa.Column('significance_sha256',sa.String(64),nullable=False),sa.Column('conservation_status',sa.String(30),nullable=False),*_ts(),sa.UniqueConstraint('organisation_id','site_slug',name='uq_heritage_site_record'))
 op.create_table('trusted_islamic_life_acceptance',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('milestone_version',sa.String(40),nullable=False),sa.Column('outcome',sa.String(20),nullable=False),sa.Column('portable_ready',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('production_ready',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('evidence_sha256',sa.String(64),nullable=False),sa.Column('notes',sa.Text()),*_ts(),sa.UniqueConstraint('organisation_id','milestone_version',name='uq_trusted_islamic_life_acceptance'))
def downgrade():
 op.drop_table('trusted_islamic_life_acceptance');op.drop_table('heritage_site_records')
