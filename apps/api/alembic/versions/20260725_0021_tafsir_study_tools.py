"""tafsir study tools

Revision ID: 20260725_0021
Revises: 20260725_0020
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20260725_0021'; down_revision='20260725_0020'; branch_labels=None; depends_on=None

def upgrade():
    uuid=postgresql.UUID(as_uuid=True)
    op.create_table('tafsir_bookmarks',sa.Column('id',uuid,primary_key=True),sa.Column('user_id',uuid,sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('tafsir_entry_id',uuid,sa.ForeignKey('tafsir_entries.id',ondelete='CASCADE'),nullable=False),sa.Column('note',sa.Text()),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('user_id','tafsir_entry_id'))
    op.create_index('ix_tafsir_bookmarks_user_id','tafsir_bookmarks',['user_id']); op.create_index('ix_tafsir_bookmarks_tafsir_entry_id','tafsir_bookmarks',['tafsir_entry_id'])
    op.create_table('tafsir_study_notes',sa.Column('id',uuid,primary_key=True),sa.Column('user_id',uuid,sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('tafsir_entry_id',uuid,sa.ForeignKey('tafsir_entries.id',ondelete='CASCADE'),nullable=False),sa.Column('title',sa.String(240)),sa.Column('body',sa.Text(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_tafsir_study_notes_user_id','tafsir_study_notes',['user_id']); op.create_index('ix_tafsir_study_notes_tafsir_entry_id','tafsir_study_notes',['tafsir_entry_id']); op.create_index('ix_tafsir_study_notes_user_entry','tafsir_study_notes',['user_id','tafsir_entry_id'])
    op.create_table('tafsir_study_collections',sa.Column('id',uuid,primary_key=True),sa.Column('user_id',uuid,sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('name',sa.String(240),nullable=False),sa.Column('description',sa.Text()),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('user_id','name'))
    op.create_index('ix_tafsir_study_collections_user_id','tafsir_study_collections',['user_id'])
    op.create_table('tafsir_study_collection_items',sa.Column('id',uuid,primary_key=True),sa.Column('collection_id',uuid,sa.ForeignKey('tafsir_study_collections.id',ondelete='CASCADE'),nullable=False),sa.Column('tafsir_entry_id',uuid,sa.ForeignKey('tafsir_entries.id',ondelete='CASCADE'),nullable=False),sa.Column('sort_order',sa.Integer(),nullable=False,server_default='0'),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('collection_id','tafsir_entry_id'))
    op.create_index('ix_tafsir_study_collection_items_collection_id','tafsir_study_collection_items',['collection_id']); op.create_index('ix_tafsir_study_collection_items_tafsir_entry_id','tafsir_study_collection_items',['tafsir_entry_id'])
    op.create_table('tafsir_study_progress',sa.Column('id',uuid,primary_key=True),sa.Column('user_id',uuid,sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('tafsir_entry_id',uuid,sa.ForeignKey('tafsir_entries.id',ondelete='CASCADE'),nullable=False),sa.Column('status',sa.String(24),nullable=False,server_default='not_started'),sa.Column('progress_percent',sa.Integer(),nullable=False,server_default='0'),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('user_id','tafsir_entry_id'),sa.CheckConstraint("status IN ('not_started','in_progress','completed')",name='ck_tafsir_study_progress_status'),sa.CheckConstraint('progress_percent BETWEEN 0 AND 100',name='ck_tafsir_study_progress_percent'))
    op.create_index('ix_tafsir_study_progress_user_id','tafsir_study_progress',['user_id']); op.create_index('ix_tafsir_study_progress_tafsir_entry_id','tafsir_study_progress',['tafsir_entry_id'])

def downgrade():
    for table in ['tafsir_study_progress','tafsir_study_collection_items','tafsir_study_collections','tafsir_study_notes','tafsir_bookmarks']: op.drop_table(table)
