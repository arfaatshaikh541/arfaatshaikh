"""learning experience
Revision ID: 20260725_0029
Revises: 20260725_0028
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20260725_0029'; down_revision='20260725_0028'; branch_labels=None; depends_on=None
def common(): return [sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()'))]
def upgrade():
 u=postgresql.UUID(as_uuid=True)
 op.create_table('learner_notes',sa.Column('id',u,primary_key=True),sa.Column('user_id',u,sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('lesson_id',u,sa.ForeignKey('lessons.id',ondelete='CASCADE'),nullable=False),sa.Column('body',sa.Text(),nullable=False),sa.Column('private',sa.Boolean(),nullable=False,server_default=sa.text('true')),sa.Column('eligible_as_evidence',sa.Boolean(),nullable=False,server_default=sa.text('false')),*common())
 op.create_index('ix_learner_notes_user_lesson','learner_notes',['user_id','lesson_id'])
 op.create_table('learning_certificates',sa.Column('id',u,primary_key=True),sa.Column('user_id',u,sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),sa.Column('course_id',u,sa.ForeignKey('courses.id',ondelete='RESTRICT'),nullable=False),sa.Column('course_version',sa.Integer(),nullable=False),sa.Column('verification_code',sa.String(64),nullable=False),sa.Column('learner_name',sa.String(240),nullable=False),sa.Column('disclaimer',sa.Text(),nullable=False),sa.Column('revoked',sa.Boolean(),nullable=False,server_default=sa.text('false')),*common(),sa.UniqueConstraint('verification_code',name='uq_learning_certificate_code'))
 op.create_table('guardian_relationships',sa.Column('id',u,primary_key=True),sa.Column('guardian_user_id',u,sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('child_user_id',u,sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='pending'),*common(),sa.UniqueConstraint('guardian_user_id','child_user_id',name='uq_guardian_child'),sa.CheckConstraint('guardian_user_id <> child_user_id',name='guardian_not_child'))
 op.create_table('learning_recommendation_events',sa.Column('id',u,primary_key=True),sa.Column('user_id',u,sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('course_id',u,sa.ForeignKey('courses.id',ondelete='CASCADE'),nullable=False),sa.Column('reason_code',sa.String(48),nullable=False),sa.Column('algorithm_version',sa.String(32),nullable=False),sa.Column('score',sa.Integer(),nullable=False),*common())
def downgrade(): op.drop_table('learning_recommendation_events'); op.drop_table('guardian_relationships'); op.drop_table('learning_certificates'); op.drop_index('ix_learner_notes_user_lesson',table_name='learner_notes'); op.drop_table('learner_notes')
