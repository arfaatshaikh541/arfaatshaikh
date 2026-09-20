from __future__ import annotations

import pytest

from aura_core.executive import GoalEngine, GoalNotReadyError


def make_engine(tmp_path) -> GoalEngine:
    return GoalEngine(f"sqlite:///{tmp_path}/goals.db")


def test_create_goal_starts_as_draft(tmp_path):
    engine = make_engine(tmp_path)
    goal = engine.create("Reach AED 100,000 MRR")
    assert goal.status == "draft"


def test_activate_fails_without_required_fields(tmp_path):
    engine = make_engine(tmp_path)
    goal = engine.create("Reach AED 100,000 MRR")
    with pytest.raises(GoalNotReadyError) as exc_info:
        engine.activate(goal.id)
    assert "success_metric" in str(exc_info.value)
    assert "budget" in str(exc_info.value)
    assert "stop_conditions" in str(exc_info.value)


def test_activate_succeeds_once_fully_specified(tmp_path):
    engine = make_engine(tmp_path)
    goal = engine.create(
        "Reach AED 100,000 MRR",
        success_metric="MRR >= 100000 AED",
        budget={"marketing_aed_per_month": 5000},
        stop_conditions=["pause if CAC exceeds 3x LTV"],
    )
    activated = engine.activate(goal.id)
    assert activated.status == "active"


def test_partial_fields_still_reported_missing(tmp_path):
    engine = make_engine(tmp_path)
    goal = engine.create("Reach AED 100,000 MRR", success_metric="MRR >= 100000 AED")
    with pytest.raises(GoalNotReadyError) as exc_info:
        engine.activate(goal.id)
    assert "success_metric" not in str(exc_info.value)
    assert "budget" in str(exc_info.value)


def test_update_progress_clamps_to_0_1(tmp_path):
    engine = make_engine(tmp_path)
    goal = engine.create("g", success_metric="m", budget={}, stop_conditions=["s"])
    engine.update_progress(goal.id, 1.5)
    assert engine.get(goal.id).progress == 1.0
    engine.update_progress(goal.id, -0.5)
    assert engine.get(goal.id).progress == 0.0


def test_due_for_review_uses_review_interval(tmp_path):
    engine = make_engine(tmp_path)
    goal = engine.create(
        "g", success_metric="m", budget={}, stop_conditions=["s"], review_interval_seconds=0,
    )
    engine.activate(goal.id)
    due = engine.due_for_review()
    assert len(due) == 1
    assert due[0].id == goal.id


def test_not_due_for_review_before_interval_elapses(tmp_path):
    engine = make_engine(tmp_path)
    goal = engine.create(
        "g", success_metric="m", budget={}, stop_conditions=["s"], review_interval_seconds=3600,
    )
    engine.activate(goal.id)
    assert engine.due_for_review() == []


def test_paused_goal_is_not_due_for_review(tmp_path):
    engine = make_engine(tmp_path)
    goal = engine.create("g", success_metric="m", budget={}, stop_conditions=["s"], review_interval_seconds=0)
    engine.activate(goal.id)
    engine.pause(goal.id)
    assert engine.due_for_review() == []


def test_mark_reviewed_resets_the_due_clock(tmp_path):
    engine = make_engine(tmp_path)
    goal = engine.create("g", success_metric="m", budget={}, stop_conditions=["s"], review_interval_seconds=3600)
    engine.activate(goal.id)
    engine.mark_reviewed(goal.id)
    assert engine.due_for_review() == []
