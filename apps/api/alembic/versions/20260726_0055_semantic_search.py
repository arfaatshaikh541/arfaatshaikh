"""Milestone 14
Revision ID: 20260726_0055
Revises: 20260726_0054
"""
from alembic import op
import sqlalchemy as sa
revision='20260726_0055'
down_revision='20260726_0054'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('semantic_indexes',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('slug',sa.String(100),nullable=False),sa.Column('version',sa.String(40),nullable=False),sa.Column('content_type',sa.String(40),nullable=False),sa.Column('model_sha256',sa.String(64),nullable=False),sa.Column('index_sha256',sa.String(64),nullable=False),sa.Column('source_coverage_percent',sa.Integer(),nullable=False),sa.Column('status',sa.String(16),nullable=False,server_default='building'),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.UniqueConstraint('organisation_id','slug','version',name='uq_semantic_index_version'))
    op.create_table('search_corpus_shards',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('semantic_index_id',sa.Uuid(),sa.ForeignKey('semantic_indexes.id',ondelete='CASCADE'),nullable=False),sa.Column('shard_key',sa.String(100),nullable=False),sa.Column('document_count',sa.Integer(),nullable=False),sa.Column('shard_sha256',sa.String(64),nullable=False),sa.Column('storage_uri',sa.String(500),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.UniqueConstraint('semantic_index_id','shard_key',name='uq_search_corpus_shard_key'))
    op.create_table('search_quality_evaluations',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('semantic_index_id',sa.Uuid(),sa.ForeignKey('semantic_indexes.id',ondelete='CASCADE'),nullable=False),sa.Column('precision_at_10',sa.Integer(),nullable=False),sa.Column('recall_at_10',sa.Integer(),nullable=False),sa.Column('grounding_rate',sa.Integer(),nullable=False),sa.Column('harmful_result_rate',sa.Integer(),nullable=False),sa.Column('outcome',sa.String(16),nullable=False),sa.Column('evidence_sha256',sa.String(64),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
def downgrade():
    op.drop_table('search_quality_evaluations')
    op.drop_table('search_corpus_shards')
    op.drop_table('semantic_indexes')
