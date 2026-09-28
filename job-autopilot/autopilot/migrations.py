"""Ordered, idempotent schema migrations for existing deployments.

New tables are created by ``Base.metadata.create_all``; this module handles changes
to tables that already exist (added columns, backfills). Each migration runs once,
inside a transaction, and is recorded in ``schema_migrations``.
"""
from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.engine import Engine

MIGRATIONS: list[tuple[str, list[str]]] = [
    ("0001_applications_submit_clicked_at", [
        "ALTER TABLE applications ADD COLUMN IF NOT EXISTS submit_clicked_at TIMESTAMPTZ",
        # Backfill: any application that ever entered SUBMITTING had its submit control clicked.
        """UPDATE applications a SET submit_clicked_at = e.ts
           FROM (SELECT application_id, MIN(ts) AS ts FROM application_events
                 WHERE to_status = 'SUBMITTING' GROUP BY application_id) e
           WHERE a.id = e.application_id AND a.submit_clicked_at IS NULL""",
    ]),
    ("0002_platforms_capabilities", [
        "ALTER TABLE platforms ADD COLUMN IF NOT EXISTS capabilities JSONB NOT NULL DEFAULT '{}'::jsonb",
    ]),
]


def run_migrations(engine: Engine) -> list[str]:
    applied: list[str] = []
    with engine.begin() as c:
        c.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (id VARCHAR(64) PRIMARY KEY, "
                       "applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"))
        # Serialise concurrent starters (web + scheduler + workers boot together).
        c.execute(text("SELECT pg_advisory_xact_lock(4242001)"))
        done = {r[0] for r in c.execute(text("SELECT id FROM schema_migrations"))}
        pending = [m for m in MIGRATIONS if m[0] not in done]
        if not pending:  # common case: take no table locks at all
            return applied
        for mid, stmts in pending:
            for sql in stmts:
                m = re.match(r"ALTER TABLE (\w+) ADD COLUMN IF NOT EXISTS (\w+)", sql)
                if m and c.execute(text("SELECT 1 FROM information_schema.columns WHERE table_name=:t "
                                        "AND column_name=:c"), {"t": m.group(1), "c": m.group(2)}).first():
                    continue  # column already there: skip the ACCESS EXCLUSIVE lock an ALTER would take
                c.execute(text(sql))
            c.execute(text("INSERT INTO schema_migrations (id) VALUES (:i)"), {"i": mid})
            applied.append(mid)
    return applied
