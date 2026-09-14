"""Milestone 18 policy and operations
Revision ID: 20260726_0072
Revises: 20260726_0071
"""
from alembic import op
import sqlalchemy as sa
revision='20260726_0072';down_revision='20260726_0071';branch_labels=None;depends_on=None
def _ts():return [sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]
def upgrade():
 op.create_table('strategic_policies',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('policy_slug',sa.String(120),nullable=False),sa.Column('version',sa.String(40),nullable=False),sa.Column('policy_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='draft'),*_ts(),sa.UniqueConstraint('organisation_id','policy_slug','version',name='uq_strategic_policy_version'))
 op.create_table('policy_lifecycle_reviews',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('policy_id',sa.Uuid(),sa.ForeignKey('strategic_policies.id',ondelete='CASCADE'),nullable=False),sa.Column('review_type',sa.String(40),nullable=False),sa.Column('reviewer_reference',sa.String(180),nullable=False),sa.Column('evidence_sha256',sa.String(64),nullable=False),sa.Column('outcome',sa.String(20),nullable=False),*_ts())
 op.create_table('operational_intelligence_profiles',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('profile_slug',sa.String(120),nullable=False),sa.Column('version',sa.String(40),nullable=False),sa.Column('metrics_coverage_percent',sa.Integer(),nullable=False),sa.Column('trace_coverage_percent',sa.Integer(),nullable=False),sa.Column('forecast_accuracy_percent',sa.Integer(),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='draft'),*_ts(),sa.UniqueConstraint('organisation_id','profile_slug','version',name='uq_operational_intelligence_profile'))
 op.create_table('operational_intelligence_decisions',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('profile_id',sa.Uuid(),sa.ForeignKey('operational_intelligence_profiles.id',ondelete='CASCADE'),nullable=False),sa.Column('decision_type',sa.String(80),nullable=False),sa.Column('inputs_json',sa.JSON(),nullable=False,server_default='{}'),sa.Column('human_override_used',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('evidence_sha256',sa.String(64),nullable=False),*_ts())
def downgrade():
 op.drop_table('operational_intelligence_decisions');op.drop_table('operational_intelligence_profiles');op.drop_table('policy_lifecycle_reviews');op.drop_table('strategic_policies')
