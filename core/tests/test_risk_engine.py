from __future__ import annotations

from aura_core.governance.risk_engine import ActionRequest, RiskEngine, RiskTier


def test_known_red_action_type():
    engine = RiskEngine()
    result = engine.classify(ActionRequest(action_type="finance.change_bank_details"))
    assert result.tier == RiskTier.RED


def test_known_amber_action_type():
    engine = RiskEngine()
    result = engine.classify(ActionRequest(action_type="social.publish"))
    assert result.tier == RiskTier.AMBER


def test_known_green_action_type():
    engine = RiskEngine()
    result = engine.classify(ActionRequest(action_type="status.read"))
    assert result.tier == RiskTier.GREEN


def test_unknown_action_type_fails_safe_to_amber():
    engine = RiskEngine()
    result = engine.classify(ActionRequest(action_type="something.nobody.registered"))
    assert result.tier == RiskTier.AMBER


def test_nonzero_amount_is_never_below_amber_even_for_unlisted_type():
    engine = RiskEngine()
    result = engine.classify(ActionRequest(action_type="finance.pay_invoice", amount=50.0))
    assert result.tier == RiskTier.AMBER


def test_green_action_type_stays_green_even_with_zero_amount():
    engine = RiskEngine()
    result = engine.classify(ActionRequest(action_type="status.read", amount=0))
    assert result.tier == RiskTier.GREEN
