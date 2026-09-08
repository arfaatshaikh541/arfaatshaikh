from __future__ import annotations

import json

import pytest

from aura_core.executive import (
    STANDARD_DEPARTMENTS,
    GoalEngine,
    MandateEngine,
    MandateNotReadyError,
    UnrecognizedDirectiveError,
    parse_run_directive,
)
from aura_core.memory import MemoryStore


def make_stack(tmp_path):
    db_url = f"sqlite:///{tmp_path}/mandates.db"
    return MandateEngine(db_url), GoalEngine(db_url), MemoryStore(db_url)


def test_a_mandate_cannot_activate_without_objectives_kpis_and_constraints(tmp_path):
    """Mirrors GoalEngine's own activation gate: an autonomous directive
    with no stated objective, no way to measure it, and no constraint on
    how it may pursue it is a liability, not a shortcut to "autonomy"."""
    mandates, _goals, _memory = make_stack(tmp_path)
    mandate = mandates.create("Run Gridkeep", mission="Keep the business moving.")

    with pytest.raises(MandateNotReadyError, match="objectives.*kpis.*constraints"):
        mandates.activate(mandate.id)

    assert mandates.get(mandate.id).status == "draft"


def test_a_fully_specified_mandate_activates(tmp_path):
    mandates, _goals, _memory = make_stack(tmp_path)
    mandate = mandates.create(
        "Run Gridkeep", mission="Keep the business moving.",
        objectives=["Answer every client inquiry within a day"],
        kpis=[{"name": "response_time_hours", "target": 24, "current": 0}],
        constraints=["never send an email without a human-reviewed template on file"],
    )

    activated = mandates.activate(mandate.id)

    assert activated.status == "active"
    assert mandate.id in [m.id for m in mandates.list_active()]


def test_parse_run_directive_recognizes_run_and_operate_but_nothing_else():
    assert parse_run_directive("Run Gridkeep") == "Gridkeep"
    assert parse_run_directive("run gridkeep") == "gridkeep"
    assert parse_run_directive("Operate Gridkeep") == "Gridkeep"
    assert parse_run_directive("Tell me about Gridkeep") is None
    assert parse_run_directive("") is None


def test_create_from_directive_scaffolds_departments_without_a_goal_form(tmp_path):
    mandates, _goals, _memory = make_stack(tmp_path)

    mandate = mandates.create_from_directive("Run Gridkeep")

    assert mandate.title == "Run Gridkeep"
    assert mandate.mission == "Operate and grow Gridkeep"
    assert mandate.status == "draft"
    objectives = mandates.get(mandate.id)
    assert len(json.loads(objectives.objectives_json)) == len(STANDARD_DEPARTMENTS)
    assert any("Sales" in o for o in json.loads(objectives.objectives_json))


def test_create_from_directive_still_requires_kpis_and_constraints_to_activate(tmp_path):
    # Departments are a generic scaffold, not real facts about the real
    # business -- KPIs/constraints for the actual company are still
    # required, honestly, before this mandate may ever run autonomously.
    mandates, _goals, _memory = make_stack(tmp_path)
    mandate = mandates.create_from_directive("Run Gridkeep")

    with pytest.raises(MandateNotReadyError, match="kpis.*constraints"):
        mandates.activate(mandate.id)


def test_create_from_directive_rejects_an_unrecognized_directive(tmp_path):
    mandates, _goals, _memory = make_stack(tmp_path)

    with pytest.raises(UnrecognizedDirectiveError):
        mandates.create_from_directive("What's up with Gridkeep")


def test_create_from_directive_survives_a_restart(tmp_path):
    # "Restart AURA and prove the mandate survives" -- a fresh
    # MandateEngine against the same database_url is exactly what a
    # process restart looks like from the caller's side.
    db_url = f"sqlite:///{tmp_path}/restart.db"
    mandates = MandateEngine(db_url)
    created = mandates.create_from_directive("Run Gridkeep")

    reopened = MandateEngine(db_url)
    reloaded = reopened.get(created.id)

    assert reloaded is not None
    assert reloaded.title == "Run Gridkeep"
    assert reloaded.mission == "Operate and grow Gridkeep"


def test_due_for_observation_respects_the_interval(tmp_path):
    mandates, _goals, _memory = make_stack(tmp_path)
    due = mandates.create(
        "due", mission="m", objectives=["o"], kpis=[{"name": "k", "target": 1, "current": 0}],
        constraints=["c"], observation_interval_seconds=0,
    )
    not_due = mandates.create(
        "not due", mission="m", objectives=["o"], kpis=[{"name": "k", "target": 1, "current": 0}],
        constraints=["c"], observation_interval_seconds=3600,
    )
    mandates.activate(due.id)
    mandates.activate(not_due.id)

    due_ids = [m.id for m in mandates.due_for_observation()]

    assert due.id in due_ids
    assert not_due.id not in due_ids


def test_record_observation_updates_summary_and_next_actions(tmp_path):
    mandates, _goals, _memory = make_stack(tmp_path)
    mandate = mandates.create(
        "m", mission="m", objectives=["o"], kpis=[{"name": "k", "target": 1, "current": 0}],
        constraints=["c"], observation_interval_seconds=3600,
    )
    mandates.activate(mandate.id)
    assert mandates.get(mandate.id).latest_summary is None

    mandates.record_observation(mandate.id, summary="all quiet", next_actions=["follow up with Acme"])

    refreshed = mandates.get(mandate.id)
    assert refreshed.latest_summary == "all quiet"
    assert refreshed.last_observed_at is not None
    # A 3600s interval means it's genuinely not due again immediately
    # after being observed just now.
    assert mandate.id not in [m.id for m in mandates.due_for_observation()]


def test_report_buckets_workstreams_by_real_status_and_surfaces_blockers(tmp_path):
    """The executive-grade "what's the update on Gridkeep" answer must
    come from real, current workstream state -- not a cached narrative
    that can silently drift out of sync."""
    mandates, goals, memory = make_stack(tmp_path)
    mandate = mandates.create(
        "Run Gridkeep", mission="m", objectives=["o"],
        kpis=[{"name": "k", "target": 1, "current": 0}], constraints=["c"],
    )
    mandates.activate(mandate.id)

    done = goals.create("send the invoice", success_metric="sent", budget={}, stop_conditions=["s"])
    goals.activate(done.id)
    goals.set_mandate(done.id, mandate.id)
    goals.complete(done.id)

    blocked = goals.create("call the client", success_metric="called", budget={}, stop_conditions=["s"])
    goals.activate(blocked.id)
    goals.set_mandate(blocked.id, mandate.id)
    goals.mark_blocked(blocked.id)
    memory.record_decision(goal=blocked.id, statement="denied: no autonomy for telephony.call", reasoning="r", source="operating_loop")

    waiting = goals.create("wait for reply", success_metric="replied", budget={}, stop_conditions=["s"])
    goals.activate(waiting.id)
    goals.set_mandate(waiting.id, mandate.id)
    goals.mark_waiting_external(waiting.id)

    report = mandates.report(mandate.id, goals, memory)

    assert report.counts == {"DONE": 1, "FAILED": 1, "WAITING_ON_EXTERNAL": 1}
    assert len(report.blockers) == 1
    assert "call the client" in report.blockers[0]
    blocked_summary = next(w for w in report.workstreams if w.goal_id == blocked.id)
    assert blocked_summary.latest_decision is not None
    assert "denied" in blocked_summary.latest_decision
