"""Milestone 14
Revision ID: 20260726_0054
Revises: 20260726_0053
"""
from alembic import op
import sqlalchemy as sa
revision='20260726_0054'
down_revision='20260726_0053'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('preservation_archives',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('slug',sa.String(100),nullable=False),sa.Column('version',sa.String(40),nullable=False),sa.Column('content_type',sa.String(40),nullable=False),sa.Column('manifest_sha256',sa.String(64),nullable=False),sa.Column('source_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(16),nullable=False,server_default='building'),sa.Column('retention_years',sa.Integer(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.UniqueConstraint('organisation_id','slug','version',name='uq_preservation_archive_version'))
    op.create_table('archive_objects',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('archive_id',sa.Uuid(),sa.ForeignKey('preservation_archives.id',ondelete='CASCADE'),nullable=False),sa.Column('object_path',sa.String(500),nullable=False),sa.Column('object_sha256',sa.String(64),nullable=False),sa.Column('size_bytes',sa.Integer(),nullable=False),sa.Column('media_type',sa.String(120)),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.UniqueConstraint('archive_id','object_path',name='uq_archive_object_path'))
    op.create_table('archive_replicas',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('archive_id',sa.Uuid(),sa.ForeignKey('preservation_archives.id',ondelete='CASCADE'),nullable=False),sa.Column('region',sa.String(40),nullable=False),sa.Column('provider_slug',sa.String(100),nullable=False),sa.Column('endpoint_url',sa.String(500),nullable=False),sa.Column('air_gapped',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('status',sa.String(16),nullable=False,server_default='pending'),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.UniqueConstraint('archive_id','region','provider_slug',name='uq_archive_replica_location'))
    op.create_table('archive_fixity_checks',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('archive_id',sa.Uuid(),sa.ForeignKey('preservation_archives.id',ondelete='CASCADE'),nullable=False),sa.Column('expected_sha256',sa.String(64),nullable=False),sa.Column('observed_sha256',sa.String(64),nullable=False),sa.Column('outcome',sa.String(16),nullable=False),sa.Column('objects_verified',sa.Integer(),nullable=False),sa.Column('unreadable_objects',sa.Integer(),nullable=False,server_default='0'),sa.Column('evidence_json',sa.JSON(),nullable=False,server_default='{}'),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
def downgrade():
    op.drop_table('archive_fixity_checks')
    op.drop_table('archive_replicas')
    op.drop_table('archive_objects')
    op.drop_table('preservation_archives')
