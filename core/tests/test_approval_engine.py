from __future__ import annotations

from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.risk_engine import ActionRequest, RiskTier


def make_engine(tmp_path) -> ApprovalEngine:
    return ApprovalEngine(f"sqlite:///{tmp_path}/approvals.db")


def test_create_and_list_pending(tmp_path):
    engine = make_engine(tmp_path)
    request = ActionRequest(action_type="social.publish", params={"post": "hello"}, amount=None)
    record = engine.create(request, RiskTier.AMBER, "requires approval per policy")

    pending = engine.pending()
    assert len(pending) == 1
    assert pending[0].id == record.id
    assert pending[0].status == "pending"


def test_decide_approved_removes_from_pending(tmp_path):
    engine = make_engine(tmp_path)
    request = ActionRequest(action_type="social.publish", params={})
    record = engine.create(request, RiskTier.AMBER, "reason")

    engine.decide(record.id, approved=True, decided_by="owner")

    assert engine.pending() == []
    refreshed = engine.get(record.id)
    assert refreshed.status == "approved"
    assert refreshed.decided_by == "owner"


def test_to_action_request_round_trips_params_amount_and_budget(tmp_path):
    engine = make_engine(tmp_path)
    original = ActionRequest(
        action_type="marketing.spend", params={"campaign": "launch"},
        requested_by="owner", amount=42.5, budget_key="marketing.q1",
    )
    record = engine.create(original, RiskTier.AMBER, "over budget")

    rebuilt = engine.to_action_request(record)
    assert rebuilt.action_type == "marketing.spend"
    assert rebuilt.params == {"campaign": "launch"}
    assert rebuilt.amount == 42.5
    assert rebuilt.budget_key == "marketing.q1"
