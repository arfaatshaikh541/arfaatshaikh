"""Additive, non-destructive schema migration.

Every stateful subsystem (memory, world model, audit log, policy engine,
task engine, mandate/goal engines, guardian, enrollment, approvals) calls
`ensure_schema(engine)` at startup instead of a bare
`Base.metadata.create_all(engine)`. `create_all()` alone only ever
creates *missing tables* -- it silently does nothing to a table that
already exists, even if the current model has since gained a column. An
owner upgrading AURA to a version whose models added a column to an
existing table would otherwise hit a real "no such column" error against
their real, already-populated database the first time that column is
read or written.

`ensure_schema()` closes that gap: after `create_all()` handles brand-new
tables, it inspects every already-existing table and adds any column
present in the current model but missing from the real on-disk table,
via SQLite's own `ALTER TABLE ... ADD COLUMN` -- never a table drop,
never a rebuild, never touching a single existing row.

This works within SQLite's real, documented constraints on ALTER TABLE
(https://www.sqlite.org/lang_altertable.html): it can add a column, but
not add a NOT NULL column with no default to a table that already has
rows. A newly-added column is therefore always created nullable at the
SQLite level regardless of the model's own nullability, with existing
rows honestly getting NULL there (they predate the column) rather than a
fabricated default -- the model's Python-level default still applies to
every row written after the migration.
"""
from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from .models import Base


def ensure_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # just created above by create_all(), already complete
            existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                ddl_type = column.type.compile(engine.dialect)
                connection.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {ddl_type}'))
