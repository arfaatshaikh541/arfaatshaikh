"""curriculum governance
Revision ID: 20260725_0027
Revises: 20260725_0026
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20260725_0027'; down_revision='20260725_0026'; branch_labels=None; depends_on=None
def common(): return [sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()'))]
def upgrade():
 u=postgresql.UUID(as_uuid=True)
 op.create_table('content_reviews',sa.Column('id',u,primary_key=True),sa.Column('content_type',sa.String(32),nullable=False),sa.Column('content_id',u,nullable=False),sa.Column('review_type',sa.String(24),nullable=False),sa.Column('reviewer_user_id',u,sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),sa.Column('author_user_id',u,sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),sa.Column('decision',sa.String(24),nullable=False,server_default='pending'),sa.Column('rationale',sa.Text()),*common())
 op.create_table('lesson_translations',sa.Column('id',u,primary_key=True),sa.Column('lesson_id',u,sa.ForeignKey('lessons.id',ondelete='CASCADE'),nullable=False),sa.Column('language',sa.String(8),nullable=False),sa.Column('version',sa.Integer(),nullable=False),sa.Column('title',sa.String(240),nullable=False),sa.Column('structure_sha256',sa.String(64),nullable=False),sa.Column('evidence_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(32),nullable=False,server_default='draft'),*common(),sa.UniqueConstraint('lesson_id','language','version',name='uq_lesson_translation_version'))
def downgrade(): op.drop_table('lesson_translations'); op.drop_table('content_reviews')
