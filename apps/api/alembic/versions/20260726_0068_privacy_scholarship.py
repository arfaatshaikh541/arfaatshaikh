"""Milestone 17
Revision ID: 20260726_0068
Revises: 20260726_0067
"""
from alembic import op
import sqlalchemy as sa
revision='20260726_0068';down_revision='20260726_0067';branch_labels=None;depends_on=None
def _ts():return [sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]
def upgrade():
 op.create_table('data_sharing_agreements',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('network_id',sa.Uuid(),sa.ForeignKey('federation_networks.id',ondelete='CASCADE'),nullable=False),sa.Column('agreement_slug',sa.String(100),nullable=False),sa.Column('version',sa.String(40),nullable=False),sa.Column('purpose',sa.Text(),nullable=False),sa.Column('retention_days',sa.Integer(),nullable=False),sa.Column('policy_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='draft'),*_ts(),sa.UniqueConstraint('network_id','agreement_slug','version',name='uq_data_sharing_agreement_version'))
 op.create_table('consent_receipts',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('agreement_id',sa.Uuid(),sa.ForeignKey('data_sharing_agreements.id',ondelete='CASCADE'),nullable=False),sa.Column('subject_reference',sa.String(160),nullable=False),sa.Column('purposes_json',sa.JSON(),nullable=False,server_default='{}'),sa.Column('receipt_sha256',sa.String(64),nullable=False),sa.Column('withdrawn',sa.Boolean(),nullable=False,server_default=sa.false()),*_ts(),sa.UniqueConstraint('agreement_id','subject_reference','receipt_sha256',name='uq_consent_receipt'))
 op.create_table('cross_border_scholarly_projects',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('network_id',sa.Uuid(),sa.ForeignKey('federation_networks.id',ondelete='CASCADE'),nullable=False),sa.Column('project_slug',sa.String(100),nullable=False),sa.Column('title',sa.String(240),nullable=False),sa.Column('methodology_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='draft'),*_ts(),sa.UniqueConstraint('network_id','project_slug',name='uq_cross_border_project_slug'))
 op.create_table('cross_border_scholar_participants',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('project_id',sa.Uuid(),sa.ForeignKey('cross_border_scholarly_projects.id',ondelete='CASCADE'),nullable=False),sa.Column('scholar_profile_id',sa.Uuid(),sa.ForeignKey('scholar_profiles.id',ondelete='CASCADE'),nullable=False),sa.Column('institution_id',sa.Uuid(),sa.ForeignKey('institutions.id',ondelete='CASCADE'),nullable=False),sa.Column('role',sa.String(60),nullable=False),sa.Column('conflict_disclosed',sa.Boolean(),nullable=False,server_default=sa.false()),*_ts(),sa.UniqueConstraint('project_id','scholar_profile_id',name='uq_cross_border_scholar'))
def downgrade():
 op.drop_table('cross_border_scholar_participants')
 op.drop_table('cross_border_scholarly_projects')
 op.drop_table('consent_receipts')
 op.drop_table('data_sharing_agreements')
