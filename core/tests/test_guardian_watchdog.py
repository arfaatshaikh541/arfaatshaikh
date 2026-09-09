"""GuardianWatchdog's own logic, in-process for speed and determinism --
the genuinely out-of-process proof (a real separate OS process engaging
the kill switch on a database it shares with nothing else) lives in
test_guardian_watchdog_subprocess.py."""
from __future__ import annotations

import time

from aura_core.governance.action_broker import ActionBroker
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import ActionRequest, RiskEngine
from aura_core.guardian import GuardianWatchdog, SecurityGuardian


def make_stack(tmp_path):
    db_url = f"sqlite:///{tmp_path}/watchdog.db"
    policy = PolicyEngine(db_url)
    audit = AuditLog(db_url)
    # Deliberately NOT wiring guardian.evaluate as the broker's on_audit
    # hook -- that's exactly the single-process coupling this watchdog
    # exists to not depend on.
    broker = ActionBroker(policy, RiskEngine(), ApprovalEngine(db_url), CredentialBroker(), audit)
    guardian = SecurityGuardian(audit, policy, db_url)
    return broker, policy, audit, guardian


def test_poll_once_returns_whatever_the_guardian_found(tmp_path):
    broker, policy, _audit, guardian = make_stack(tmp_path)
    watchdog = GuardianWatchdog(guardian, poll_interval_seconds=0.1)

    policy.set_autonomy_level("finance.change_bank_details", 5)
    for _ in range(3):
        broker.submit(ActionRequest(action_type="finance.change_bank_details"))

    events = watchdog.poll_once()

    assert any(e.rule_name == "red_tier_velocity" for e in events)
    assert watchdog.polls_run == 1


def test_the_background_thread_engages_the_kill_switch_with_no_on_audit_hook_at_all(tmp_path):
    """The whole point: nothing in the broker's own submit() path calls
    the guardian. Only the watchdog's independent polling loop does, and
    it still catches the burst and freezes the system."""
    broker, policy, _audit, guardian = make_stack(tmp_path)
    watchdog = GuardianWatchdog(guardian, poll_interval_seconds=0.1)

    policy.set_autonomy_level("finance.change_bank_details", 5)
    for _ in range(3):
        broker.submit(ActionRequest(action_type="finance.change_bank_details"))
    assert policy.is_kill_switch_engaged() is False  # not yet -- nothing has polled

    watchdog.start_in_background()
    try:
        deadline = time.time() + 5
        while not policy.is_kill_switch_engaged() and time.time() < deadline:
            time.sleep(0.05)
        assert policy.is_kill_switch_engaged() is True
        assert watchdog.polls_run >= 1
    finally:
        watchdog.stop()
