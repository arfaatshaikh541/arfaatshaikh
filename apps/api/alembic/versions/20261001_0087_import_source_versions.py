"""Record which adapter produced an import and the source version, retrieval time and checksum it retrieved."""
from alembic import op

revision = "20261001_0087"
down_revision = "20261001_0086"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for statement in (
        "ALTER TABLE data_set_imports ADD COLUMN adapter_id VARCHAR(80)",
        "ALTER TABLE data_set_imports ADD COLUMN source_version VARCHAR(160)",
        "ALTER TABLE data_set_imports ADD COLUMN source_retrieved_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE data_set_imports ADD COLUMN source_checksum VARCHAR(64)",
    ):
        bind.exec_driver_sql(statement)


def downgrade() -> None:
    op.get_bind().exec_driver_sql("ALTER TABLE data_set_imports DROP COLUMN source_checksum, DROP COLUMN source_retrieved_at, DROP COLUMN source_version, DROP COLUMN adapter_id")
