"""Milestone 17
Revision ID: 20260726_0069
Revises: 20260726_0068
"""
from alembic import op
import sqlalchemy as sa
revision='20260726_0069';down_revision='20260726_0068';branch_labels=None;depends_on=None
def _ts():return [sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]
def upgrade():
 op.create_table('federation_resilience_exercises',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('network_id',sa.Uuid(),sa.ForeignKey('federation_networks.id',ondelete='CASCADE'),nullable=False),sa.Column('scenario',sa.String(160),nullable=False),sa.Column('healthy_nodes',sa.Integer(),nullable=False),sa.Column('recovery_minutes',sa.Integer(),nullable=False),sa.Column('evidence_sha256',sa.String(64),nullable=False),sa.Column('outcome',sa.String(20),nullable=False),*_ts())
 op.create_table('federation_transparency_reports',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('network_id',sa.Uuid(),sa.ForeignKey('federation_networks.id',ondelete='CASCADE'),nullable=False),sa.Column('report_slug',sa.String(100),nullable=False),sa.Column('version',sa.String(40),nullable=False),sa.Column('publication_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='draft'),*_ts(),sa.UniqueConstraint('network_id','report_slug','version',name='uq_federation_transparency_version'))
 op.create_table('federation_audit_reviews',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('network_id',sa.Uuid(),sa.ForeignKey('federation_networks.id',ondelete='CASCADE'),nullable=False),sa.Column('member_coverage_percent',sa.Integer(),nullable=False),sa.Column('critical_findings',sa.Integer(),nullable=False),sa.Column('evidence_sha256',sa.String(64),nullable=False),sa.Column('outcome',sa.String(20),nullable=False),*_ts())
 op.create_table('global_ummah_network_acceptance',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('network_id',sa.Uuid(),sa.ForeignKey('federation_networks.id',ondelete='CASCADE'),nullable=False),sa.Column('milestone_version',sa.String(40),nullable=False),sa.Column('outcome',sa.String(20),nullable=False),sa.Column('portable_ready',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('production_ready',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('evidence_sha256',sa.String(64),nullable=False),sa.Column('notes',sa.Text()),*_ts(),sa.UniqueConstraint('network_id','milestone_version',name='uq_global_ummah_acceptance_version'))
def downgrade():
 op.drop_table('global_ummah_network_acceptance')
 op.drop_table('federation_audit_reviews')
 op.drop_table('federation_transparency_reports')
 op.drop_table('federation_resilience_exercises')
