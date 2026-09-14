"""Milestone 19 halal and commerce
Revision ID: 20260726_0075
Revises: 20260726_0074
"""
from alembic import op
import sqlalchemy as sa
revision='20260726_0075';down_revision='20260726_0074';branch_labels=None;depends_on=None
def _ts():return [sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]
def upgrade():
 op.create_table('halal_standards',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('standard_slug',sa.String(120),nullable=False),sa.Column('version',sa.String(40),nullable=False),sa.Column('standard_sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(20),nullable=False,server_default='draft'),*_ts(),sa.UniqueConstraint('organisation_id','standard_slug','version',name='uq_halal_standard'))
 op.create_table('halal_certification_records',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('standard_id',sa.Uuid(),sa.ForeignKey('halal_standards.id',ondelete='CASCADE'),nullable=False),sa.Column('certificate_reference',sa.String(180),nullable=False),sa.Column('certifier_reference',sa.String(180),nullable=False),sa.Column('certificate_sha256',sa.String(64),nullable=False),sa.Column('revoked',sa.Boolean(),nullable=False,server_default=sa.false()),*_ts(),sa.UniqueConstraint('standard_id','certificate_reference',name='uq_halal_certificate_reference'))
 op.create_table('product_traceability_records',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('certification_id',sa.Uuid(),sa.ForeignKey('halal_certification_records.id',ondelete='CASCADE'),nullable=False),sa.Column('product_reference',sa.String(180),nullable=False),sa.Column('traceability_percent',sa.Integer(),nullable=False),sa.Column('supply_chain_json',sa.JSON(),nullable=False,server_default='{}'),sa.Column('evidence_sha256',sa.String(64),nullable=False),*_ts())
 op.create_table('ethical_commerce_reviews',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id',ondelete='CASCADE'),nullable=False),sa.Column('merchant_reference',sa.String(180),nullable=False),sa.Column('traceability_percent',sa.Integer(),nullable=False),sa.Column('evidence_sha256',sa.String(64),nullable=False),sa.Column('outcome',sa.String(20),nullable=False),*_ts())
def downgrade():
 op.drop_table('ethical_commerce_reviews');op.drop_table('product_traceability_records');op.drop_table('halal_certification_records');op.drop_table('halal_standards')
