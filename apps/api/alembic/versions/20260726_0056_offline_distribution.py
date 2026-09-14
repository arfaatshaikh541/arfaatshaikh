"""Milestone 14
Revision ID: 20260726_0056
Revises: 20260726_0055
"""
from alembic import op
import sqlalchemy as sa
revision='20260726_0056'
down_revision='20260726_0055'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('offline_distribution_packages',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('package_slug',sa.String(100),nullable=False),sa.Column('version',sa.String(40),nullable=False),sa.Column('manifest_sha256',sa.String(64),nullable=False),sa.Column('package_sha256',sa.String(64),nullable=False),sa.Column('size_mb',sa.Integer(),nullable=False),sa.Column('status',sa.String(16),nullable=False,server_default='draft'),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.UniqueConstraint('organisation_id','package_slug','version',name='uq_offline_package_version'))
    op.create_table('offline_package_releases',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('package_id',sa.Uuid(),sa.ForeignKey('offline_distribution_packages.id',ondelete='CASCADE'),nullable=False),sa.Column('channel',sa.String(40),nullable=False),sa.Column('signature_sha256',sa.String(64),nullable=False),sa.Column('expires_at_iso',sa.String(40),nullable=False),sa.Column('revocation_list_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(16),nullable=False,server_default='pending'),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_table('offline_update_deltas',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('base_package_id',sa.Uuid(),sa.ForeignKey('offline_distribution_packages.id',ondelete='CASCADE'),nullable=False),sa.Column('target_package_id',sa.Uuid(),sa.ForeignKey('offline_distribution_packages.id',ondelete='CASCADE'),nullable=False),sa.Column('delta_sha256',sa.String(64),nullable=False),sa.Column('size_mb',sa.Integer(),nullable=False),sa.Column('rollback_sha256',sa.String(64),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.UniqueConstraint('base_package_id','target_package_id',name='uq_offline_update_transition'))
def downgrade():
    op.drop_table('offline_update_deltas')
    op.drop_table('offline_package_releases')
    op.drop_table('offline_distribution_packages')
