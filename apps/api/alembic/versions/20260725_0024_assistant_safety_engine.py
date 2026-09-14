"""assistant safety and immutable audit
Revision ID: 20260725_0024
Revises: 20260725_0023
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20260725_0024'; down_revision='20260725_0023'; branch_labels=None; depends_on=None

def upgrade():
    u=postgresql.UUID(as_uuid=True); ts=lambda: sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()'))
    op.create_table('assistant_safety_policies',sa.Column('id',u,primary_key=True),sa.Column('policy_key',sa.String(80),nullable=False),sa.Column('version',sa.String(64),nullable=False),sa.Column('category',sa.String(48),nullable=False),sa.Column('active',sa.Boolean(),nullable=False,server_default=sa.text('false')),sa.Column('rules_json',sa.Text(),nullable=False),ts(),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),sa.UniqueConstraint('policy_key','version',name='uq_assistant_safety_policy_version'))
    op.create_table('assistant_policy_decisions',sa.Column('id',u,primary_key=True),sa.Column('answer_run_id',u,sa.ForeignKey('assistant_answer_runs.id',ondelete='SET NULL')),sa.Column('policy_version',sa.String(64),nullable=False),sa.Column('action',sa.String(20),nullable=False),sa.Column('category',sa.String(48),nullable=False),sa.Column('reasons_json',sa.Text(),nullable=False),sa.Column('raw_question_retention_days',sa.Integer(),nullable=False),ts(),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')))
    op.create_table('assistant_answer_audit_log',sa.Column('id',u,primary_key=True),sa.Column('answer_run_id',u,sa.ForeignKey('assistant_answer_runs.id',ondelete='RESTRICT'),nullable=False),sa.Column('version',sa.Integer(),nullable=False),sa.Column('event_type',sa.String(48),nullable=False),sa.Column('payload_sha256',sa.String(64),nullable=False),sa.Column('previous_entry_sha256',sa.String(64)),sa.Column('entry_sha256',sa.String(64),nullable=False),ts(),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),sa.UniqueConstraint('answer_run_id','version',name='uq_assistant_audit_version'))
    op.execute("CREATE FUNCTION prevent_assistant_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'assistant audit log is append-only'; END; $$")
    op.execute("CREATE TRIGGER assistant_audit_no_update BEFORE UPDATE OR DELETE ON assistant_answer_audit_log FOR EACH ROW EXECUTE FUNCTION prevent_assistant_audit_mutation()")

def downgrade():
    op.execute('DROP TRIGGER IF EXISTS assistant_audit_no_update ON assistant_answer_audit_log'); op.execute('DROP FUNCTION IF EXISTS prevent_assistant_audit_mutation()'); op.drop_table('assistant_answer_audit_log'); op.drop_table('assistant_policy_decisions'); op.drop_table('assistant_safety_policies')
