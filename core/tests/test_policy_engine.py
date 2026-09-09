from __future__ import annotations

from aura_core.governance.policy_engine import PolicyDecision, PolicyEngine
from aura_core.governance.risk_engine import ActionRequest, RiskTier


def make_engine(tmp_path) -> PolicyEngine:
    return PolicyEngine(f"sqlite:///{tmp_path}/policy.db")


def test_unknown_action_type_defaults_to_level_zero_and_denies(tmp_path):
    engine = make_engine(tmp_path)
    evaluation = engine.evaluate(ActionRequest(action_type="never.configured"), RiskTier.GREEN)
    assert evaluation.autonomy_level == 0
    assert evaluation.decision == PolicyDecision.DENY


def test_level_four_green_action_is_allowed(tmp_path):
    engine = make_engine(tmp_path)
    engine.set_autonomy_level("status.read", 4)
    evaluation = engine.evaluate(ActionRequest(action_type="status.read"), RiskTier.GREEN)
    assert evaluation.decision == PolicyDecision.ALLOW


def test_level_three_amber_action_requires_approval(tmp_path):
    engine = make_engine(tmp_path)
    engine.set_autonomy_level("social.publish", 3)
    evaluation = engine.evaluate(ActionRequest(action_type="social.publish"), RiskTier.AMBER)
    assert evaluation.decision == PolicyDecision.REQUIRE_APPROVAL


def test_red_tier_always_requires_approval_even_at_level_five(tmp_path):
    engine = make_engine(tmp_path)
    engine.set_autonomy_level("finance.change_bank_details", 5)
    evaluation = engine.evaluate(ActionRequest(action_type="finance.change_bank_details"), RiskTier.RED)
    assert evaluation.decision == PolicyDecision.REQUIRE_APPROVAL


def test_prohibited_action_is_always_denied_regardless_of_level(tmp_path):
    engine = make_engine(tmp_path)
    engine.set_autonomy_level("marketing.spend", 5)
    engine.prohibit("marketing.spend", "owner froze all marketing spend this quarter")
    evaluation = engine.evaluate(ActionRequest(action_type="marketing.spend"), RiskTier.AMBER)
    assert evaluation.decision == PolicyDecision.DENY
    assert "froze" in evaluation.reason


def test_budget_exceeded_escalates_allow_to_require_approval(tmp_path):
    engine = make_engine(tmp_path)
    engine.set_autonomy_level("marketing.spend", 4)
    engine.set_budget("marketing.q1", limit_amount=100.0)

    within_budget = engine.evaluate(
        ActionRequest(action_type="marketing.spend", amount=50.0, budget_key="marketing.q1"),
        RiskTier.AMBER,
    )
    assert within_budget.decision == PolicyDecision.ALLOW

    engine.record_spend("marketing.q1", 50.0)

    over_budget = engine.evaluate(
        ActionRequest(action_type="marketing.spend", amount=60.0, budget_key="marketing.q1"),
        RiskTier.AMBER,
    )
    assert over_budget.decision == PolicyDecision.REQUIRE_APPROVAL
    assert "exceeds remaining budget" in over_budget.reason


def test_kill_switch_engage_and_disengage(tmp_path):
    engine = make_engine(tmp_path)
    assert engine.is_kill_switch_engaged() is False
    engine.engage_kill_switch()
    assert engine.is_kill_switch_engaged() is True
    engine.disengage_kill_switch()
    assert engine.is_kill_switch_engaged() is False


def test_seeded_policy_survives_reopening_the_same_database(tmp_path):
    db_url = f"sqlite:///{tmp_path}/policy_persist.db"
    engine_a = PolicyEngine(db_url)
    engine_a.set_autonomy_level("status.read", 4)
    engine_a.engage_kill_switch()

    engine_b = PolicyEngine(db_url)  # simulates a process restart
    assert engine_b.get_autonomy_level("status.read") == 4
    assert engine_b.is_kill_switch_engaged() is True
