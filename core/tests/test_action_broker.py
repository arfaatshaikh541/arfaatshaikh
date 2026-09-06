from __future__ import annotations

from aura_core.governance.action_broker import ActionBroker, HandlerResult, OutcomeStatus
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import ActionRequest, RiskEngine
from aura_core.status import CapabilityStatus


def make_broker(tmp_path) -> tuple[ActionBroker, PolicyEngine, AuditLog]:
    db_url = f"sqlite:///{tmp_path}/broker.db"
    policy = PolicyEngine(db_url)
    risk = RiskEngine()
    approvals = ApprovalEngine(db_url)
    credentials = CredentialBroker()
    audit = AuditLog(db_url)
    broker = ActionBroker(policy, risk, approvals, credentials, audit)
    return broker, policy, audit


def test_green_action_at_level_four_executes_immediately(tmp_path):
    broker, policy, audit = make_broker(tmp_path)
    policy.set_autonomy_level("status.read", 4)
    broker.register_handler("status.read", lambda r: HandlerResult(CapabilityStatus.LIVE, "ok"))

    outcome = broker.submit(ActionRequest(action_type="status.read"))

    assert outcome.status == OutcomeStatus.EXECUTED
    assert audit.verify_chain().valid is True
    assert audit.verify_chain().entries_checked == 1


def test_amber_action_at_low_level_requires_approval_then_executes_on_approve(tmp_path):
    broker, policy, audit = make_broker(tmp_path)
    policy.set_autonomy_level("social.publish", 2)
    executed = {"count": 0}

    def handler(_request: ActionRequest) -> HandlerResult:
        executed["count"] += 1
        return HandlerResult(CapabilityStatus.LIVE, "published")

    broker.register_handler("social.publish", handler)

    outcome = broker.submit(ActionRequest(action_type="social.publish", params={"post": "hi"}))
    assert outcome.status == OutcomeStatus.PENDING_APPROVAL
    assert executed["count"] == 0  # must not execute before approval

    resumed = broker.resume_after_approval(outcome.approval_id, approved=True, decided_by="owner")
    assert resumed.status == OutcomeStatus.EXECUTED
    assert executed["count"] == 1


def test_denied_approval_never_executes_the_handler(tmp_path):
    broker, policy, _audit = make_broker(tmp_path)
    policy.set_autonomy_level("social.publish", 2)
    executed = {"count": 0}
    broker.register_handler("social.publish", lambda r: executed.update(count=executed["count"] + 1) or HandlerResult(CapabilityStatus.LIVE, "x"))

    outcome = broker.submit(ActionRequest(action_type="social.publish"))
    resumed = broker.resume_after_approval(outcome.approval_id, approved=False, decided_by="owner")

    assert resumed.status == OutcomeStatus.DENIED
    assert executed["count"] == 0


def test_red_action_requires_approval_even_at_level_five(tmp_path):
    broker, policy, _audit = make_broker(tmp_path)
    policy.set_autonomy_level("finance.change_bank_details", 5)
    broker.register_handler("finance.change_bank_details", lambda r: HandlerResult(CapabilityStatus.LIVE, "changed"))

    outcome = broker.submit(ActionRequest(action_type="finance.change_bank_details"))

    assert outcome.status == OutcomeStatus.PENDING_APPROVAL


def test_kill_switch_blocks_execution_even_at_level_five_green(tmp_path):
    broker, policy, audit = make_broker(tmp_path)
    policy.set_autonomy_level("status.read", 5)
    broker.register_handler("status.read", lambda r: HandlerResult(CapabilityStatus.LIVE, "ok"))
    policy.engage_kill_switch()

    outcome = broker.submit(ActionRequest(action_type="status.read"))

    assert outcome.status == OutcomeStatus.KILL_SWITCH_ENGAGED
    assert audit.all_entries()[-1].decision == "KILL_SWITCH"


def test_kill_switch_engaged_between_approval_and_resume_blocks_execution(tmp_path):
    broker, policy, _audit = make_broker(tmp_path)
    policy.set_autonomy_level("social.publish", 2)
    broker.register_handler("social.publish", lambda r: HandlerResult(CapabilityStatus.LIVE, "x"))

    outcome = broker.submit(ActionRequest(action_type="social.publish"))
    policy.engage_kill_switch()
    resumed = broker.resume_after_approval(outcome.approval_id, approved=True, decided_by="owner")

    assert resumed.status == OutcomeStatus.KILL_SWITCH_ENGAGED


def test_prohibited_action_is_denied_without_reaching_the_handler(tmp_path):
    broker, policy, _audit = make_broker(tmp_path)
    policy.set_autonomy_level("marketing.spend", 5)
    policy.prohibit("marketing.spend", "owner froze spend")
    called = {"yes": False}
    broker.register_handler("marketing.spend", lambda r: called.update(yes=True) or HandlerResult(CapabilityStatus.LIVE, "x"))

    outcome = broker.submit(ActionRequest(action_type="marketing.spend", amount=10, budget_key="mk"))

    assert outcome.status == OutcomeStatus.DENIED
    assert called["yes"] is False


def test_no_handler_registered_reports_no_handler_not_a_false_success(tmp_path):
    broker, policy, _audit = make_broker(tmp_path)
    policy.set_autonomy_level("email.send_external", 4)

    outcome = broker.submit(ActionRequest(action_type="email.send_external"))

    assert outcome.status == OutcomeStatus.NO_HANDLER


def test_not_connected_handler_result_is_reported_honestly_not_as_executed(tmp_path):
    broker, policy, _audit = make_broker(tmp_path)
    policy.set_autonomy_level("computer_control.open_app", 4)
    broker.register_handler(
        "computer_control.open_app",
        lambda r: HandlerResult(CapabilityStatus.NOT_CONNECTED, "no native agent on this machine"),
    )

    outcome = broker.submit(ActionRequest(action_type="computer_control.open_app"))

    assert outcome.status == OutcomeStatus.DENIED
    assert "NOT_CONNECTED" in outcome.message


def test_budget_spend_is_recorded_only_on_successful_execution(tmp_path):
    broker, policy, _audit = make_broker(tmp_path)
    policy.set_autonomy_level("marketing.spend", 4)
    policy.set_budget("mk", 100.0)
    broker.register_handler("marketing.spend", lambda r: HandlerResult(CapabilityStatus.LIVE, "spent"))

    broker.submit(ActionRequest(action_type="marketing.spend", amount=30.0, budget_key="mk"))

    assert policy.remaining_budget("mk") == 70.0


def test_every_branch_produces_exactly_one_audit_entry(tmp_path):
    broker, policy, audit = make_broker(tmp_path)
    policy.set_autonomy_level("status.read", 4)
    broker.register_handler("status.read", lambda r: HandlerResult(CapabilityStatus.LIVE, "ok"))

    broker.submit(ActionRequest(action_type="status.read"))       # ALLOW -> EXECUTED
    broker.submit(ActionRequest(action_type="unregistered.type"))  # unknown -> AMBER -> level 0 -> DENY
    policy.engage_kill_switch()
    broker.submit(ActionRequest(action_type="status.read"))       # KILL_SWITCH_ENGAGED

    entries = audit.all_entries()
    assert len(entries) == 3
    assert audit.verify_chain().valid is True
