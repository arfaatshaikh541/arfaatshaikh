"""Milestone 20 security and release
Revision ID: 20260726_0079
Revises: 20260726_0078
"""
from alembic import op
import sqlalchemy as sa
revision='20260726_0079';down_revision='20260726_0078';branch_labels=None;depends_on=None
def _ts():return [sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]
def upgrade():
 op.create_table('security_posture_reviews',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('audit_coverage_percent',sa.Integer(),nullable=False),sa.Column('critical_vulnerabilities',sa.Integer(),nullable=False),sa.Column('high_vulnerabilities',sa.Integer(),nullable=False),sa.Column('evidence_sha256',sa.String(64),nullable=False),sa.Column('outcome',sa.String(20),nullable=False),*_ts())
 op.create_table('compliance_control_results',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('review_id',sa.Uuid(),sa.ForeignKey('security_posture_reviews.id',ondelete='CASCADE'),nullable=False),sa.Column('control_code',sa.String(100),nullable=False),sa.Column('framework',sa.String(80),nullable=False),sa.Column('passed',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('evidence_sha256',sa.String(64),nullable=False),*_ts())
 op.create_table('release_candidates',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('release_version',sa.String(40),nullable=False),sa.Column('migration_head',sa.String(40),nullable=False),sa.Column('manifest_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='draft'),*_ts(),sa.UniqueConstraint('organisation_id','release_version',name='uq_release_candidate'))
 op.create_table('release_artifacts',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('release_id',sa.Uuid(),sa.ForeignKey('release_candidates.id',ondelete='CASCADE'),nullable=False),sa.Column('artifact_name',sa.String(180),nullable=False),sa.Column('artifact_type',sa.String(60),nullable=False),sa.Column('artifact_sha256',sa.String(64),nullable=False),sa.Column('signed',sa.Boolean(),nullable=False,server_default=sa.false()),*_ts())
 op.create_table('software_bills_of_materials',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('release_id',sa.Uuid(),sa.ForeignKey('release_candidates.id',ondelete='CASCADE'),nullable=False),sa.Column('format_name',sa.String(40),nullable=False),sa.Column('component_count',sa.Integer(),nullable=False),sa.Column('document_sha256',sa.String(64),nullable=False),sa.Column('verified',sa.Boolean(),nullable=False,server_default=sa.false()),*_ts())
def downgrade():
 op.drop_table('software_bills_of_materials');op.drop_table('release_artifacts');op.drop_table('release_candidates');op.drop_table('compliance_control_results');op.drop_table('security_posture_reviews')
