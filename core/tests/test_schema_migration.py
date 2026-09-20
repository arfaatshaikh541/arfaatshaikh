"""ensure_schema() closes a real gap: SQLAlchemy's own
Base.metadata.create_all() only ever creates missing tables -- it does
nothing to a table that already exists, even when the current model has
since gained a column. These tests build a genuinely old on-disk SQLite
schema by hand (the exact "intentionally OLD database schema" scenario),
insert real data into it exactly as an older AURA version would have,
then run ensure_schema() and prove the upgrade is non-destructive: old
data survives, the new column exists afterward, and the ORM can read and
write through it normally.
"""
from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from aura_core.governance.models import AuditEntry
from aura_core.memory.schema_migration import ensure_schema


def _make_old_audit_entries_table(engine) -> None:
    """An "old" audit_entries table missing the `result_message` column
    the current AuditEntry model has -- built with raw SQL, not the ORM,
    so this genuinely does not depend on the current model definition at
    all, matching a real prior version's on-disk shape."""
    with engine.begin() as connection:
        connection.execute(text(
            """
            CREATE TABLE audit_entries (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                id VARCHAR(36),
                timestamp_iso VARCHAR(40),
                actor VARCHAR(200),
                action_type VARCHAR(150),
                params_json TEXT,
                risk_tier VARCHAR(10),
                decision VARCHAR(30),
                approval_id VARCHAR(36),
                result_status VARCHAR(30),
                prev_hash VARCHAR(64),
                hash VARCHAR(64)
            )
            """
        ))
        connection.execute(text(
            """
            INSERT INTO audit_entries
                (id, timestamp_iso, actor, action_type, params_json, risk_tier,
                 decision, approval_id, result_status, prev_hash, hash)
            VALUES
                ('old-1', '2025-01-01T00:00:00+00:00', 'owner', 'status.read', '{}', 'GREEN',
                 'ALLOW', NULL, 'EXECUTED', '0000000000000000000000000000000000000000000000000000000000000000', 'deadbeef')
            """
        ))


def test_ensure_schema_adds_a_missing_column_without_touching_existing_rows(tmp_path):
    db_path = tmp_path / "old_audit.db"
    engine = create_engine(f"sqlite:///{db_path}")
    _make_old_audit_entries_table(engine)

    # Save -> close -> reopen, exactly like restarting AURA between an old
    # and new version.
    engine.dispose()
    engine = create_engine(f"sqlite:///{db_path}")

    ensure_schema(engine)

    with engine.connect() as connection:
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(audit_entries)"))}
    assert "result_message" in columns

    Session = sessionmaker(bind=engine)
    with Session() as session:
        old_row = session.get(AuditEntry, 1)
        assert old_row is not None
        assert old_row.id == "old-1"
        assert old_row.actor == "owner"
        assert old_row.result_message is None  # honestly unknown for pre-migration rows, not fabricated

        new_row = AuditEntry(
            id="new-1", timestamp_iso="2026-01-01T00:00:00+00:00", actor="owner",
            action_type="status.read", params_json="{}", risk_tier="GREEN", decision="ALLOW",
            result_status="EXECUTED", result_message="ok", prev_hash="deadbeef", hash="cafebabe",
        )
        session.add(new_row)
        session.commit()

    with Session() as session:
        assert session.get(AuditEntry, 1).id == "old-1"
        fetched_new = session.get(AuditEntry, 2)
        assert fetched_new.result_message == "ok"


def test_ensure_schema_is_idempotent_and_safe_to_rerun(tmp_path):
    db_path = tmp_path / "rerun.db"
    engine = create_engine(f"sqlite:///{db_path}")
    _make_old_audit_entries_table(engine)

    ensure_schema(engine)
    ensure_schema(engine)  # must not error re-adding a column that now exists, or touch data

    Session = sessionmaker(bind=engine)
    with Session() as session:
        assert session.get(AuditEntry, 1).id == "old-1"


def test_ensure_schema_still_creates_brand_new_tables(tmp_path):
    db_path = tmp_path / "fresh.db"
    engine = create_engine(f"sqlite:///{db_path}")

    ensure_schema(engine)

    with engine.connect() as connection:
        tables = {row[0] for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    assert "audit_entries" in tables
