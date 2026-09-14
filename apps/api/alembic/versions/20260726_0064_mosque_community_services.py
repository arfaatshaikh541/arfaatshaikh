"""Milestone 16 mosque and community services
Revision ID: 20260726_0064
Revises: 20260726_0063
"""
from alembic import op
import sqlalchemy as sa
revision='20260726_0064'; down_revision='20260726_0063'; branch_labels=None; depends_on=None
def _ts():return [sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]
def upgrade():
 op.create_table('mosque_services',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('institution_id',sa.Uuid(),sa.ForeignKey('institutions.id',ondelete='CASCADE'),nullable=False),sa.Column('service_slug',sa.String(100),nullable=False),sa.Column('service_type',sa.String(40),nullable=False),sa.Column('title',sa.String(200),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='draft'),*_ts(),sa.UniqueConstraint('institution_id','service_slug',name='uq_mosque_service_slug'))
 op.create_table('volunteer_profiles',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('user_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('identity_verified',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('safeguarding_accepted',sa.Boolean(),nullable=False,server_default=sa.false()),*_ts(),sa.UniqueConstraint('organisation_id','user_id',name='uq_volunteer_profile_user'))
 op.create_table('volunteer_assignments',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('service_id',sa.Uuid(),sa.ForeignKey('mosque_services.id',ondelete='CASCADE'),nullable=False),sa.Column('volunteer_profile_id',sa.Uuid(),sa.ForeignKey('volunteer_profiles.id',ondelete='CASCADE'),nullable=False),sa.Column('role',sa.String(80),nullable=False),sa.Column('maximum_weekly_hours',sa.Integer(),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='planned'),*_ts(),sa.UniqueConstraint('service_id','volunteer_profile_id',name='uq_volunteer_assignment'))
 op.create_table('service_referrals',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('referral_key',sa.String(160),nullable=False),sa.Column('source_service_id',sa.Uuid(),sa.ForeignKey('mosque_services.id',ondelete='SET NULL')),sa.Column('receiving_institution_id',sa.Uuid(),sa.ForeignKey('institutions.id'),nullable=False),sa.Column('evidence_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='pending'),*_ts(),sa.UniqueConstraint('organisation_id','referral_key',name='uq_service_referral_key'))
def downgrade():
 for t in ['service_referrals','volunteer_assignments','volunteer_profiles','mosque_services']:op.drop_table(t)
