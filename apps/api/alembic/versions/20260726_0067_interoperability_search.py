"""Milestone 17
Revision ID: 20260726_0067
Revises: 20260726_0066
"""
from alembic import op
import sqlalchemy as sa
revision='20260726_0067';down_revision='20260726_0066';branch_labels=None;depends_on=None
def _ts():return [sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]
def upgrade():
 op.create_table('interoperability_profiles',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('network_id',sa.Uuid(),sa.ForeignKey('federation_networks.id',ondelete='CASCADE'),nullable=False),sa.Column('profile_slug',sa.String(100),nullable=False),sa.Column('version',sa.String(40),nullable=False),sa.Column('schema_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='draft'),*_ts(),sa.UniqueConstraint('network_id','profile_slug','version',name='uq_interop_profile_version'))
 op.create_table('interoperability_conformance_runs',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('profile_id',sa.Uuid(),sa.ForeignKey('interoperability_profiles.id',ondelete='CASCADE'),nullable=False),sa.Column('member_id',sa.Uuid(),sa.ForeignKey('federation_members.id',ondelete='CASCADE'),nullable=False),sa.Column('tests_passed',sa.Integer(),nullable=False),sa.Column('tests_failed',sa.Integer(),nullable=False),sa.Column('evidence_sha256',sa.String(64),nullable=False),sa.Column('outcome',sa.String(20),nullable=False),*_ts())
 op.create_table('federated_search_nodes',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('network_id',sa.Uuid(),sa.ForeignKey('federation_networks.id',ondelete='CASCADE'),nullable=False),sa.Column('node_slug',sa.String(100),nullable=False),sa.Column('institution_id',sa.Uuid(),sa.ForeignKey('institutions.id',ondelete='CASCADE'),nullable=False),sa.Column('endpoint_fingerprint',sa.String(64),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='offline'),*_ts(),sa.UniqueConstraint('network_id','node_slug',name='uq_federated_search_node'))
 op.create_table('federated_search_evaluations',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('network_id',sa.Uuid(),sa.ForeignKey('federation_networks.id',ondelete='CASCADE'),nullable=False),sa.Column('grounding_percent',sa.Integer(),nullable=False),sa.Column('attribution_percent',sa.Integer(),nullable=False),sa.Column('harmful_rate_basis_points',sa.Integer(),nullable=False),sa.Column('p95_timeout_ms',sa.Integer(),nullable=False),sa.Column('outcome',sa.String(20),nullable=False),*_ts())
def downgrade():
 op.drop_table('federated_search_evaluations')
 op.drop_table('federated_search_nodes')
 op.drop_table('interoperability_conformance_runs')
 op.drop_table('interoperability_profiles')
