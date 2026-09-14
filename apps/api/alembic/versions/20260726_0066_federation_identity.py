"""Milestone 17
Revision ID: 20260726_0066
Revises: 20260726_0065
"""
from alembic import op
import sqlalchemy as sa
revision='20260726_0066';down_revision='20260726_0065';branch_labels=None;depends_on=None
def _ts():return [sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]
def upgrade():
 op.create_table('federation_networks',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('slug',sa.String(100),nullable=False),sa.Column('name',sa.String(200),nullable=False),sa.Column('manifest_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='draft'),*_ts(),sa.UniqueConstraint('organisation_id','slug',name='uq_federation_network_slug'))
 op.create_table('federation_members',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('network_id',sa.Uuid(),sa.ForeignKey('federation_networks.id',ondelete='CASCADE'),nullable=False),sa.Column('institution_id',sa.Uuid(),sa.ForeignKey('institutions.id',ondelete='CASCADE'),nullable=False),sa.Column('jurisdiction_code',sa.String(2),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='pending'),sa.Column('capabilities_json',sa.JSON(),nullable=False,server_default='{}'),*_ts(),sa.UniqueConstraint('network_id','institution_id',name='uq_federation_member'))
 op.create_table('federation_trust_policies',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('network_id',sa.Uuid(),sa.ForeignKey('federation_networks.id',ondelete='CASCADE'),nullable=False),sa.Column('version',sa.String(40),nullable=False),sa.Column('policy_sha256',sa.String(64),nullable=False),sa.Column('published',sa.Boolean(),nullable=False,server_default=sa.false()),*_ts(),sa.UniqueConstraint('network_id','version',name='uq_federation_trust_policy_version'))
 op.create_table('federated_identity_credentials',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('issuer_institution_id',sa.Uuid(),sa.ForeignKey('institutions.id',ondelete='CASCADE'),nullable=False),sa.Column('subject_key',sa.String(160),nullable=False),sa.Column('assurance_level',sa.Integer(),nullable=False),sa.Column('proof_sha256',sa.String(64),nullable=False),sa.Column('revoked',sa.Boolean(),nullable=False,server_default=sa.false()),*_ts(),sa.UniqueConstraint('issuer_institution_id','subject_key',name='uq_federated_identity_subject'))
def downgrade():
 op.drop_table('federated_identity_credentials')
 op.drop_table('federation_trust_policies')
 op.drop_table('federation_members')
 op.drop_table('federation_networks')
