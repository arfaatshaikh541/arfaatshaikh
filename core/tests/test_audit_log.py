from __future__ import annotations

from sqlalchemy import create_engine, text

from aura_core.governance.audit_log import AuditLog


def make_log(tmp_path) -> tuple[AuditLog, str]:
    db_url = f"sqlite:///{tmp_path}/audit.db"
    return AuditLog(db_url), db_url


def test_chain_is_valid_after_several_entries(tmp_path):
    log, _ = make_log(tmp_path)
    for i in range(5):
        log.record(
            actor="owner", action_type=f"test.action.{i}", params_json="{}",
            risk_tier="GREEN", decision="ALLOW", approval_id=None,
            result_status="EXECUTED", result_message="ok",
        )

    verification = log.verify_chain()
    assert verification.valid is True
    assert verification.entries_checked == 5


def test_tampering_with_a_past_entry_breaks_the_chain(tmp_path):
    log, db_url = make_log(tmp_path)
    for i in range(3):
        log.record(
            actor="owner", action_type=f"test.action.{i}", params_json="{}",
            risk_tier="GREEN", decision="ALLOW", approval_id=None,
            result_status="EXECUTED", result_message="ok",
        )

    # Tamper directly at the SQL level -- bypassing the AuditLog API
    # entirely, the way a compromised process with raw DB access would.
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(text("UPDATE audit_entries SET result_message = 'forged' WHERE seq = 1"))

    verification = log.verify_chain()
    assert verification.valid is False
    assert verification.broken_at_seq == 1


def test_empty_log_verifies_trivially(tmp_path):
    log, _ = make_log(tmp_path)
    verification = log.verify_chain()
    assert verification.valid is True
    assert verification.entries_checked == 0
