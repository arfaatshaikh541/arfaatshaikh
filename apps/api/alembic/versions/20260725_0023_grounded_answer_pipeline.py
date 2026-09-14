"""claim-grounded answer pipeline

Revision ID: 20260725_0023
Revises: 20260725_0022
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision='20260725_0023'; down_revision='20260725_0022'; branch_labels=None; depends_on=None


def upgrade():
    uuid=postgresql.UUID(as_uuid=True)
    op.create_table('assistant_answer_runs',
        sa.Column('id',uuid,primary_key=True),sa.Column('user_id',uuid,sa.ForeignKey('users.id',ondelete='SET NULL')),
        sa.Column('question_sha256',sa.String(64),nullable=False),sa.Column('question_language',sa.String(16),nullable=False),
        sa.Column('classification',sa.String(48),nullable=False),sa.Column('risk_level',sa.String(16),nullable=False),
        sa.Column('classifier_version',sa.String(64),nullable=False),sa.Column('grounding_policy_version',sa.String(64),nullable=False),
        sa.Column('status',sa.String(20),nullable=False,server_default='received'),sa.Column('insufficiency_reason',sa.Text()),
        sa.Column('response_text',sa.Text()),sa.Column('response_sha256',sa.String(64)),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),
        sa.CheckConstraint("status IN ('received','classified','evidence_ready','assembled','insufficient','failed')",name='ck_assistant_answer_runs_status'),
        sa.CheckConstraint("risk_level IN ('standard','sensitive','high_risk')",name='ck_assistant_answer_runs_risk'))
    op.create_index('ix_assistant_answer_runs_user_created','assistant_answer_runs',['user_id','created_at'])
    op.create_table('assistant_claims',
        sa.Column('id',uuid,primary_key=True),sa.Column('answer_run_id',uuid,sa.ForeignKey('assistant_answer_runs.id',ondelete='CASCADE'),nullable=False),
        sa.Column('position',sa.Integer(),nullable=False),sa.Column('claim_type',sa.String(40),nullable=False),sa.Column('text',sa.Text(),nullable=False),
        sa.Column('text_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(16),nullable=False,server_default='proposed'),
        sa.Column('rejection_reason',sa.String(160)),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),
        sa.CheckConstraint("claim_type IN ('direct_quote','source_summary','scholarly_interpretation','difference_of_opinion','general_explanation')",name='ck_assistant_claims_type'),
        sa.CheckConstraint("status IN ('proposed','verified','rejected')",name='ck_assistant_claims_status'),
        sa.CheckConstraint('position >= 0',name='ck_assistant_claims_position'),sa.UniqueConstraint('answer_run_id','position',name='uq_assistant_claim_position'))
    op.create_table('assistant_claim_evidence',
        sa.Column('id',uuid,primary_key=True),sa.Column('claim_id',uuid,sa.ForeignKey('assistant_claims.id',ondelete='CASCADE'),nullable=False),
        sa.Column('chunk_id',uuid,sa.ForeignKey('retrieval_chunks.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('support_type',sa.String(20),nullable=False),sa.Column('citation_label',sa.String(80),nullable=False),
        sa.Column('evidence_text_sha256',sa.String(64),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),
        sa.CheckConstraint("support_type IN ('quotes','supports','attributes','contrasts')",name='ck_assistant_claim_evidence_support'),
        sa.UniqueConstraint('claim_id','chunk_id',name='uq_assistant_claim_evidence_chunk'))


def downgrade():
    op.drop_table('assistant_claim_evidence'); op.drop_table('assistant_claims'); op.drop_index('ix_assistant_answer_runs_user_created',table_name='assistant_answer_runs'); op.drop_table('assistant_answer_runs')
