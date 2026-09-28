"""Ordered, idempotent schema migrations for existing deployments.

New tables are created by ``Base.metadata.create_all``; this module handles changes
to tables that already exist (added columns, backfills). Each migration runs once,
inside a transaction, and is recorded in ``schema_migrations``.
"""
from __future__ import annotations

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
        for mid, stmts in MIGRATIONS:
            if mid in done:
                continue
            for sql in stmts:
                c.execute(text(sql))
            c.execute(text("INSERT INTO schema_migrations (id) VALUES (:i)"), {"i": mid})
            applied.append(mid)
    return applied
