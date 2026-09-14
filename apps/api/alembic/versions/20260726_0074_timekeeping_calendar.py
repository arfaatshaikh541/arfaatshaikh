"""Milestone 19 timekeeping and calendar
Revision ID: 20260726_0074
Revises: 20260726_0073
"""
from alembic import op
import sqlalchemy as sa
revision='20260726_0074';down_revision='20260726_0073';branch_labels=None;depends_on=None
def _ts():return [sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]
def upgrade():
 op.create_table('prayer_time_authorities',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('authority_slug',sa.String(120),nullable=False),sa.Column('jurisdiction_code',sa.String(8),nullable=False),sa.Column('verified',sa.Boolean(),nullable=False,server_default=sa.false()),*_ts(),sa.UniqueConstraint('organisation_id','authority_slug',name='uq_prayer_time_authority'))
 op.create_table('prayer_calculation_profiles',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('profile_slug',sa.String(120),nullable=False),sa.Column('version',sa.String(40),nullable=False),sa.Column('method_code',sa.String(80),nullable=False),sa.Column('manifest_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='draft'),*_ts(),sa.UniqueConstraint('organisation_id','profile_slug','version',name='uq_prayer_calculation_profile'))
 op.create_table('prayer_time_verifications',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('profile_id',sa.Uuid(),sa.ForeignKey('prayer_calculation_profiles.id',ondelete='CASCADE'),nullable=False),sa.Column('validation_percent',sa.Integer(),nullable=False),sa.Column('evidence_sha256',sa.String(64),nullable=False),sa.Column('outcome',sa.String(20),nullable=False),*_ts())
 op.create_table('hijri_calendar_authorities',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('authority_slug',sa.String(120),nullable=False),sa.Column('jurisdiction_code',sa.String(8),nullable=False),sa.Column('methodology_sha256',sa.String(64),nullable=False),sa.Column('verified',sa.Boolean(),nullable=False,server_default=sa.false()),*_ts(),sa.UniqueConstraint('organisation_id','authority_slug','jurisdiction_code',name='uq_hijri_calendar_authority'))
def downgrade():
 op.drop_table('hijri_calendar_authorities');op.drop_table('prayer_time_verifications');op.drop_table('prayer_calculation_profiles');op.drop_table('prayer_time_authorities')
