"""Milestone 16 zakat and waqf governance
Revision ID: 20260726_0062
Revises: 20260726_0061
"""
from alembic import op
import sqlalchemy as sa
revision='20260726_0062'; down_revision='20260726_0061'; branch_labels=None; depends_on=None
def _ts():return [sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]
def upgrade():
 op.create_table('zakat_funds',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('slug',sa.String(100),nullable=False),sa.Column('name',sa.String(200),nullable=False),sa.Column('evidence_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='draft'),*_ts(),sa.UniqueConstraint('organisation_id','slug',name='uq_zakat_fund_slug'))
 op.create_table('waqf_assets',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('asset_key',sa.String(160),nullable=False),sa.Column('asset_type',sa.String(40),nullable=False),sa.Column('asset_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='review'),*_ts(),sa.UniqueConstraint('organisation_id','asset_key',name='uq_waqf_asset_key'))
 op.create_table('fiduciary_audits',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('subject_type',sa.String(40),nullable=False),sa.Column('subject_id',sa.Uuid(),nullable=False),sa.Column('evidence_sha256',sa.String(64),nullable=False),sa.Column('outcome',sa.String(20),nullable=False),sa.Column('notes',sa.Text()),*_ts())
def downgrade():
 for t in ['fiduciary_audits','waqf_assets','zakat_funds']:op.drop_table(t)
