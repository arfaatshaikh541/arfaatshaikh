"""Give created_at/updated_at a database default on every table missing one.

The ORM models declare server_default=now() but several migrations created the
columns NOT NULL without it, so ORM inserts (e.g. Qur'an surahs) failed on a
real PostgreSQL database.
"""
from alembic import op

revision = "20260929_0082"
down_revision = "20260726_0081"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    DO $$
    DECLARE r record;
    BEGIN
      FOR r IN
        SELECT table_name, column_name FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND column_name IN ('created_at', 'updated_at')
          AND data_type = 'timestamp with time zone'
          AND column_default IS NULL
          AND table_name <> 'alembic_version'
      LOOP
        EXECUTE format('ALTER TABLE %I ALTER COLUMN %I SET DEFAULT now()', r.table_name, r.column_name);
      END LOOP;
    END $$;
    """)


def downgrade() -> None:
    pass
