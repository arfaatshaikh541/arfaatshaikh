"""governed retrieval foundation

Revision ID: 20260725_0022
Revises: 20260725_0021
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision='20260725_0022'; down_revision='20260725_0021'; branch_labels=None; depends_on=None


def upgrade():
    uuid=postgresql.UUID(as_uuid=True)
    op.create_table('retrieval_projection_runs',
        sa.Column('id',uuid,primary_key=True),sa.Column('corpus_type',sa.String(32),nullable=False),
        sa.Column('status',sa.String(16),nullable=False,server_default='pending'),sa.Column('policy_version',sa.String(64),nullable=False),
        sa.Column('projected_count',sa.Integer(),nullable=False,server_default='0'),sa.Column('rejected_count',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('initiated_by_user_id',uuid,sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),sa.Column('failure_reason',sa.Text()),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),
        sa.CheckConstraint("status IN ('pending','running','completed','failed','cancelled')",name='ck_retrieval_projection_runs_status'))
    op.create_table('retrieval_documents',
        sa.Column('id',uuid,primary_key=True),sa.Column('corpus_type',sa.String(32),nullable=False),sa.Column('entity_id',uuid,nullable=False),
        sa.Column('canonical_reference',sa.String(255),nullable=False),sa.Column('source_edition_id',uuid,sa.ForeignKey('source_editions.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('source_passage_id',uuid,sa.ForeignKey('source_passages.id',ondelete='RESTRICT'),nullable=False),sa.Column('content_language',sa.String(16),nullable=False),
        sa.Column('content_kind',sa.String(40),nullable=False),sa.Column('content_sha256',sa.String(64),nullable=False),sa.Column('licence_snapshot',sa.Text(),nullable=False),
        sa.Column('attribution_snapshot',sa.Text(),nullable=False),sa.Column('projection_run_id',uuid,sa.ForeignKey('retrieval_projection_runs.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('active',sa.Boolean(),nullable=False,server_default=sa.text('false')),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),
        sa.CheckConstraint("corpus_type IN ('quran','hadith','tafsir','topic','cross_reference')",name='ck_retrieval_documents_corpus_type'),
        sa.UniqueConstraint('corpus_type','entity_id','content_sha256',name='uq_retrieval_document_version'))
    op.create_index('ix_retrieval_documents_entity','retrieval_documents',['corpus_type','entity_id'])
    op.create_table('retrieval_chunks',
        sa.Column('id',uuid,primary_key=True),sa.Column('document_id',uuid,sa.ForeignKey('retrieval_documents.id',ondelete='CASCADE'),nullable=False),
        sa.Column('chunk_index',sa.Integer(),nullable=False),sa.Column('text',sa.Text(),nullable=False),sa.Column('text_sha256',sa.String(64),nullable=False),
        sa.Column('start_offset',sa.Integer(),nullable=False),sa.Column('end_offset',sa.Integer(),nullable=False),sa.Column('token_estimate',sa.Integer(),nullable=False),
        sa.Column('boundary_type',sa.String(32),nullable=False),sa.Column('active',sa.Boolean(),nullable=False,server_default=sa.text('false')),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),
        sa.CheckConstraint('chunk_index >= 0',name='ck_retrieval_chunks_index'),sa.CheckConstraint('start_offset >= 0 AND end_offset > start_offset',name='ck_retrieval_chunks_offsets'),
        sa.UniqueConstraint('document_id','chunk_index'))
    op.create_index('ix_retrieval_chunks_document_active','retrieval_chunks',['document_id','active'])
    op.create_table('retrieval_query_audits',
        sa.Column('id',uuid,primary_key=True),sa.Column('user_id',uuid,sa.ForeignKey('users.id',ondelete='SET NULL')),sa.Column('query_sha256',sa.String(64),nullable=False),
        sa.Column('query_language',sa.String(16),nullable=False),sa.Column('requested_corpora',sa.Text(),nullable=False),sa.Column('policy_version',sa.String(64),nullable=False),
        sa.Column('status',sa.String(16),nullable=False,server_default='started'),sa.Column('candidate_count',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('selected_count',sa.Integer(),nullable=False,server_default='0'),sa.Column('insufficiency_reason',sa.Text()),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),
        sa.CheckConstraint("status IN ('started','completed','insufficient','failed')",name='ck_retrieval_query_audits_status'))
    op.create_table('retrieval_evidence_selections',
        sa.Column('id',uuid,primary_key=True),sa.Column('query_audit_id',uuid,sa.ForeignKey('retrieval_query_audits.id',ondelete='CASCADE'),nullable=False),
        sa.Column('chunk_id',uuid,sa.ForeignKey('retrieval_chunks.id',ondelete='RESTRICT'),nullable=False),sa.Column('rank_position',sa.Integer(),nullable=False),
        sa.Column('retrieval_score_millis',sa.Integer(),nullable=False),sa.Column('selected',sa.Boolean(),nullable=False,server_default=sa.text('false')),
        sa.Column('rejection_reason',sa.String(120)),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),
        sa.CheckConstraint('rank_position > 0',name='ck_retrieval_evidence_selections_rank'),sa.UniqueConstraint('query_audit_id','chunk_id'))


def downgrade():
    for table in ['retrieval_evidence_selections','retrieval_query_audits','retrieval_chunks','retrieval_documents','retrieval_projection_runs']:
        op.drop_table(table)
