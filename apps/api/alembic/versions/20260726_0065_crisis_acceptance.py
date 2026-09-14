"""Milestone 16 crisis coordination and acceptance
Revision ID: 20260726_0065
Revises: 20260726_0064
"""
from alembic import op
import sqlalchemy as sa
revision='20260726_0065'; down_revision='20260726_0064'; branch_labels=None; depends_on=None
def _ts():return [sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]
def upgrade():
 op.create_table('crisis_response_plans',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('plan_slug',sa.String(100),nullable=False),sa.Column('version',sa.String(40),nullable=False),sa.Column('incident_type',sa.String(60),nullable=False),sa.Column('evidence_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='draft'),*_ts(),sa.UniqueConstraint('organisation_id','plan_slug','version',name='uq_crisis_response_plan_version'))
 op.create_table('crisis_exercises',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('plan_id',sa.Uuid(),sa.ForeignKey('crisis_response_plans.id',ondelete='CASCADE'),nullable=False),sa.Column('scenario',sa.String(120),nullable=False),sa.Column('evidence_sha256',sa.String(64),nullable=False),sa.Column('data_loss_or_harm_detected',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('outcome',sa.String(20),nullable=False),*_ts())
 op.create_table('public_service_analytics_releases',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('release_slug',sa.String(100),nullable=False),sa.Column('version',sa.String(40),nullable=False),sa.Column('k_anonymity',sa.Integer(),nullable=False),sa.Column('minimum_group_size',sa.Integer(),nullable=False),sa.Column('publication_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='draft'),*_ts(),sa.UniqueConstraint('organisation_id','release_slug','version',name='uq_public_service_analytics_version'))
 op.create_table('ummah_services_acceptance',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('milestone_version',sa.String(40),nullable=False),sa.Column('outcome',sa.String(20),nullable=False),sa.Column('portable_ready',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('production_ready',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('evidence_sha256',sa.String(64),nullable=False),sa.Column('notes',sa.Text()),*_ts(),sa.UniqueConstraint('organisation_id','milestone_version',name='uq_ummah_services_acceptance_version'))
def downgrade():
 for t in ['ummah_services_acceptance','public_service_analytics_releases','crisis_exercises','crisis_response_plans']:op.drop_table(t)
