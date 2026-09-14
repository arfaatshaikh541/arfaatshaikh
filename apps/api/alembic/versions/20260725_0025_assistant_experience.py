"""assistant conversation and feedback experience
Revision ID: 20260725_0025
Revises: 20260725_0024
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20260725_0025'; down_revision='20260725_0024'; branch_labels=None; depends_on=None

def upgrade():
    u=postgresql.UUID(as_uuid=True)
    common=[sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()'))]
    op.create_table('assistant_conversations',sa.Column('id',u,primary_key=True),sa.Column('user_id',u,sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('title',sa.String(160),nullable=False),sa.Column('locale',sa.String(8),nullable=False,server_default='en'),sa.Column('archived',sa.Boolean(),nullable=False,server_default=sa.text('false')),*common)
    op.create_index('ix_assistant_conversations_user_updated','assistant_conversations',['user_id','updated_at'])
    op.create_table('assistant_messages',sa.Column('id',u,primary_key=True),sa.Column('conversation_id',u,sa.ForeignKey('assistant_conversations.id',ondelete='CASCADE'),nullable=False),sa.Column('answer_run_id',u,sa.ForeignKey('assistant_answer_runs.id',ondelete='SET NULL')),sa.Column('position',sa.Integer(),nullable=False),sa.Column('role',sa.String(16),nullable=False),sa.Column('content',sa.Text(),nullable=False),sa.Column('content_sha256',sa.String(64),nullable=False),*common,sa.UniqueConstraint('conversation_id','position',name='uq_assistant_message_position'))
    op.create_table('assistant_feedback',sa.Column('id',u,primary_key=True),sa.Column('user_id',u,sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('answer_run_id',u,sa.ForeignKey('assistant_answer_runs.id',ondelete='CASCADE'),nullable=False),sa.Column('rating',sa.String(16),nullable=False),sa.Column('reason_code',sa.String(48)),sa.Column('comment',sa.Text()),*common,sa.UniqueConstraint('user_id','answer_run_id',name='uq_assistant_feedback_user_answer'))

def downgrade():
    op.drop_table('assistant_feedback'); op.drop_table('assistant_messages'); op.drop_index('ix_assistant_conversations_user_updated',table_name='assistant_conversations'); op.drop_table('assistant_conversations')
