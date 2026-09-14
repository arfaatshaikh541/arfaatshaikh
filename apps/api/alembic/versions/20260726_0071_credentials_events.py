"""Milestone 18 credentials and events
Revision ID: 20260726_0071
Revises: 20260726_0070
"""
from alembic import op
import sqlalchemy as sa
revision='20260726_0071';down_revision='20260726_0070';branch_labels=None;depends_on=None
def _ts():return [sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]
def upgrade():
 op.create_table('verifiable_credential_schemas',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('schema_slug',sa.String(120),nullable=False),sa.Column('version',sa.String(40),nullable=False),sa.Column('schema_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='draft'),*_ts(),sa.UniqueConstraint('organisation_id','schema_slug','version',name='uq_verifiable_credential_schema'))
 op.create_table('verifiable_credential_records',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('schema_id',sa.Uuid(),sa.ForeignKey('verifiable_credential_schemas.id',ondelete='CASCADE'),nullable=False),sa.Column('credential_reference',sa.String(180),nullable=False),sa.Column('issuer_institution_id',sa.Uuid(),sa.ForeignKey('institutions.id',ondelete='CASCADE'),nullable=False),sa.Column('subject_reference',sa.String(180),nullable=False),sa.Column('signature_sha256',sa.String(64),nullable=False),sa.Column('revoked',sa.Boolean(),nullable=False,server_default=sa.false()),*_ts(),sa.UniqueConstraint('schema_id','credential_reference',name='uq_verifiable_credential_reference'))
 op.create_table('civilizational_events',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('event_slug',sa.String(120),nullable=False),sa.Column('title',sa.String(240),nullable=False),sa.Column('jurisdiction_code',sa.String(2),nullable=False),sa.Column('programme_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='draft'),*_ts(),sa.UniqueConstraint('organisation_id','event_slug',name='uq_civilizational_event_slug'))
 op.create_table('civilizational_event_hosts',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('event_id',sa.Uuid(),sa.ForeignKey('civilizational_events.id',ondelete='CASCADE'),nullable=False),sa.Column('institution_id',sa.Uuid(),sa.ForeignKey('institutions.id',ondelete='CASCADE'),nullable=False),sa.Column('role',sa.String(60),nullable=False),sa.Column('verified',sa.Boolean(),nullable=False,server_default=sa.false()),*_ts(),sa.UniqueConstraint('event_id','institution_id',name='uq_civilizational_event_host'))
def downgrade():
 op.drop_table('civilizational_event_hosts');op.drop_table('civilizational_events');op.drop_table('verifiable_credential_records');op.drop_table('verifiable_credential_schemas')
