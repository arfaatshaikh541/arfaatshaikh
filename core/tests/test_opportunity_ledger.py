"""OpportunityLedger is a plain, honest record store -- these tests
prove records persist across a real restart (a fresh OpportunityLedger
against the same database), that opportunity and risk records are
distinguishable, and that status transitions (open -> acted_on/dismissed)
work, without any detection logic involved (there is none here -- see
the module docstring for why).
"""
from __future__ import annotations

import pytest

from aura_core.opportunities import OpportunityInput, OpportunityLedger


def test_a_recorded_opportunity_survives_a_restart(tmp_path):
    db_url = f"sqlite:///{tmp_path}/opps.db"
    ledger = OpportunityLedger(db_url)

    record = ledger.record(OpportunityInput(
        category="upsell", summary="Customer X has grown 3x usage, worth an upsell conversation",
        evidence="usage logs show 3x growth over 90 days", confidence=0.7,
        estimated_impact="medium", effort="low", recommended_next_action="schedule a call",
    ))

    reopened = OpportunityLedger(db_url)
    reloaded = reopened.get(record.id)

    assert reloaded is not None
    assert reloaded.summary == "Customer X has grown 3x usage, worth an upsell conversation"
    assert reloaded.kind == "opportunity"
    assert reloaded.status == "open"


def test_risks_and_opportunities_are_distinguishable(tmp_path):
    ledger = OpportunityLedger(f"sqlite:///{tmp_path}/opps.db")
    ledger.record(OpportunityInput(kind="opportunity", category="market", summary="new market segment"))
    ledger.record(OpportunityInput(kind="risk", category="security", summary="dependency has a known CVE"))

    opportunities = ledger.list_open(kind="opportunity")
    risks = ledger.list_open(kind="risk")

    assert len(opportunities) == 1
    assert len(risks) == 1
    assert opportunities[0].category == "market"
    assert risks[0].category == "security"


def test_set_status_moves_a_record_out_of_the_open_list(tmp_path):
    ledger = OpportunityLedger(f"sqlite:///{tmp_path}/opps.db")
    record = ledger.record(OpportunityInput(category="operational", summary="automate the weekly report"))

    ledger.set_status(record.id, "acted_on")

    assert ledger.list_open() == []
    assert ledger.get(record.id).status == "acted_on"


def test_set_status_on_an_unknown_record_is_honest(tmp_path):
    ledger = OpportunityLedger(f"sqlite:///{tmp_path}/opps.db")

    with pytest.raises(ValueError):
        ledger.set_status("does-not-exist", "dismissed")
