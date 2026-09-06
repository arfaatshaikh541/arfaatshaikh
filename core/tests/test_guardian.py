from __future__ import annotations

from aura_core.governance.action_broker import ActionBroker, HandlerResult
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import ActionRequest, RiskEngine
from aura_core.guardian import SecurityGuardian
from aura_core.status import CapabilityStatus


def make_stack(tmp_path):
    db_url = f"sqlite:///{tmp_path}/guardian.db"
    policy = PolicyEngine(db_url)
    risk = RiskEngine()
    approvals = ApprovalEngine(db_url)
    credentials = CredentialBroker()
    audit = AuditLog(db_url)
    broker = ActionBroker(policy, risk, approvals, credentials, audit)
    guardian = SecurityGuardian(audit, policy, db_url)
    return broker, policy, audit, guardian


def test_guardian_does_nothing_when_nothing_new_happened(tmp_path):
    _broker, _policy, _audit, guardian = make_stack(tmp_path)
    assert guardian.evaluate() == []


def test_guardian_freezes_on_repeated_denials(tmp_path):
    broker, policy, _audit, guardian = make_stack(tmp_path)
    # Never configured -> autonomy level 0 -> every submission is DENIED.
    for _ in range(5):
        broker.submit(ActionRequest(action_type="some.unconfigured.action", requested_by="agent-x"))

    assert policy.is_kill_switch_engaged() is False  # broker itself doesn't freeze anything

    events = guardian.evaluate()

    assert policy.is_kill_switch_engaged() is True
    assert len(events) == 1
    assert events[0].rule_name == "repeated_denials"
    assert events[0].action_taken == "KILL_SWITCH_ENGAGED"


def test_guardian_freezes_on_red_tier_velocity(tmp_path):
    broker, policy, _audit, guardian = make_stack(tmp_path)
    policy.set_autonomy_level("finance.change_bank_details", 5)  # RED always needs approval anyway
    for _ in range(3):
        broker.submit(ActionRequest(action_type="finance.change_bank_details"))

    events = guardian.evaluate()

    assert policy.is_kill_switch_engaged() is True
    assert any(e.rule_name == "red_tier_velocity" for e in events)


def test_guardian_debounces_the_same_rule_within_the_window(tmp_path):
    # evaluate() looks at a rolling time window, not "only entries since
    # the last call" -- necessary because it's invoked after every single
    # audit write (see the on_audit hook in runtime.py), so a strictly
    # incremental watermark would only ever see a batch of one entry and
    # no threshold rule could ever fire. The tradeoff is debouncing: the
    # same still-true condition must not spam a fresh event every call.
    broker, policy, _audit, guardian = make_stack(tmp_path)
    for _ in range(5):
        broker.submit(ActionRequest(action_type="some.unconfigured.action"))

    first_pass = guardian.evaluate()
    assert len(first_pass) == 1
    assert policy.is_kill_switch_engaged() is True

    second_pass = guardian.evaluate()  # same entries, still within the window
    assert second_pass == []  # debounced, not re-fired
    assert policy.is_kill_switch_engaged() is True  # still frozen from the first firing


def test_guardian_logs_only_if_a_rule_already_froze_it_in_the_same_batch(tmp_path):
    # The kill switch is checked first on every submit(), so once it's
    # engaged nothing later can even reach risk/policy evaluation (that's
    # the point). The only way to see two rules fire in one evaluate()
    # call is two different rules tripping on the *same* batch of prior
    # entries: the first engages the switch, the second sees it already
    # engaged and only logs.
    broker, policy, _audit, guardian = make_stack(tmp_path)
    policy.set_autonomy_level("finance.change_bank_details", 5)
    for _ in range(5):
        broker.submit(ActionRequest(action_type="some.unconfigured.action"))
    for _ in range(3):
        broker.submit(ActionRequest(action_type="finance.change_bank_details"))

    events = guardian.evaluate()

    assert [e.rule_name for e in events] == ["repeated_denials", "red_tier_velocity"]
    assert events[0].action_taken == "KILL_SWITCH_ENGAGED"
    assert events[1].action_taken == "LOGGED_ONLY"
    assert policy.is_kill_switch_engaged() is True


def test_manual_freeze_records_an_event(tmp_path):
    _broker, policy, _audit, guardian = make_stack(tmp_path)
    event = guardian.freeze("fire drill")
    assert policy.is_kill_switch_engaged() is True
    assert event.rule_name == "manual"
    assert event.detail == "fire drill"


def test_broker_rate_limits_a_single_action_type(tmp_path):
    from aura_core.governance.action_broker import OutcomeStatus
    from aura_core.governance.rate_limiter import RateLimiter

    db_url = f"sqlite:///{tmp_path}/ratelimited.db"
    policy = PolicyEngine(db_url)
    policy.set_autonomy_level("status.read", 4)
    risk = RiskEngine()
    approvals = ApprovalEngine(db_url)
    credentials = CredentialBroker()
    audit = AuditLog(db_url)
    limiter = RateLimiter(default_max_count=2, default_window_seconds=60)
    broker = ActionBroker(policy, risk, approvals, credentials, audit, rate_limiter=limiter)
    broker.register_handler("status.read", lambda r: HandlerResult(CapabilityStatus.LIVE, "ok"))

    assert broker.submit(ActionRequest(action_type="status.read")).status == OutcomeStatus.EXECUTED
    assert broker.submit(ActionRequest(action_type="status.read")).status == OutcomeStatus.EXECUTED
    third = broker.submit(ActionRequest(action_type="status.read"))
    assert third.status == OutcomeStatus.RATE_LIMITED


def test_on_audit_hook_fires_after_every_submission(tmp_path):
    db_url = f"sqlite:///{tmp_path}/onaudit.db"
    policy = PolicyEngine(db_url)
    risk = RiskEngine()
    approvals = ApprovalEngine(db_url)
    credentials = CredentialBroker()
    audit = AuditLog(db_url)
    calls = {"count": 0}
    broker = ActionBroker(policy, risk, approvals, credentials, audit, on_audit=lambda: calls.update(count=calls["count"] + 1))

    broker.submit(ActionRequest(action_type="whatever"))
    broker.submit(ActionRequest(action_type="whatever"))

    assert calls["count"] == 2
