"""Milestone 20 platform integration
Revision ID: 20260726_0078
Revises: 20260726_0077
"""
from alembic import op
import sqlalchemy as sa
revision='20260726_0078';down_revision='20260726_0077';branch_labels=None;depends_on=None
def _ts():return [sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]
def upgrade():
 op.create_table('platform_components',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('component_slug',sa.String(120),nullable=False),sa.Column('version',sa.String(40),nullable=False),sa.Column('domain_name',sa.String(120),nullable=False),sa.Column('artifact_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='draft'),*_ts(),sa.UniqueConstraint('organisation_id','component_slug','version',name='uq_platform_component'))
 op.create_table('integration_contracts',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('component_id',sa.Uuid(),sa.ForeignKey('platform_components.id',ondelete='CASCADE'),nullable=False),sa.Column('contract_name',sa.String(160),nullable=False),sa.Column('contract_version',sa.String(40),nullable=False),sa.Column('schema_sha256',sa.String(64),nullable=False),sa.Column('idempotent',sa.Boolean(),nullable=False,server_default=sa.false()),*_ts())
 op.create_table('cross_domain_verifications',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('verification_type',sa.String(80),nullable=False),sa.Column('coverage_percent',sa.Integer(),nullable=False),sa.Column('critical_failures',sa.Integer(),nullable=False),sa.Column('evidence_sha256',sa.String(64),nullable=False),sa.Column('outcome',sa.String(20),nullable=False),*_ts())
def downgrade():
 op.drop_table('cross_domain_verifications');op.drop_table('integration_contracts');op.drop_table('platform_components')
