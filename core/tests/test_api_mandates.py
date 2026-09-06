from __future__ import annotations

from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings


def test_create_activate_and_report_a_mandate_through_the_api():
    client = TestClient(create_app(load_settings()))

    create_response = client.post("/mandates", json={
        "title": "Run Gridkeep",
        "mission": "Keep Gridkeep operations moving day to day.",
        "objectives": ["Answer every client inquiry within a day"],
        "kpis": [{"name": "response_time_hours", "target": 24, "current": 0}],
        "constraints": ["never send an email without owner review"],
    })
    assert create_response.status_code == 200
    mandate_id = create_response.json()["id"]
    assert create_response.json()["status"] == "draft"

    activate_response = client.post(f"/mandates/{mandate_id}/activate")
    assert activate_response.json()["status"] == "active"

    listing = client.get("/mandates").json()
    assert len(listing) == 1
    assert listing[0]["id"] == mandate_id

    report = client.get(f"/mandates/{mandate_id}/report").json()
    assert report["title"] == "Run Gridkeep"
    assert report["counts"] == {}
    assert report["workstreams"] == []


def test_activate_without_required_fields_returns_an_error():
    client = TestClient(create_app(load_settings()))
    create_response = client.post("/mandates", json={"title": "Underspecified", "mission": "m"})
    mandate_id = create_response.json()["id"]

    activate_response = client.post(f"/mandates/{mandate_id}/activate")
    assert "error" in activate_response.json()


def test_report_for_an_unknown_mandate_is_a_404_not_a_crash():
    client = TestClient(create_app(load_settings()))
    response = client.get("/mandates/does-not-exist/report")
    assert response.status_code == 404


def test_a_goal_can_be_linked_to_a_mandate_and_shows_up_in_its_report():
    client = TestClient(create_app(load_settings()))

    mandate_id = client.post("/mandates", json={
        "title": "Run Gridkeep", "mission": "m", "objectives": ["o"],
        "kpis": [{"name": "k", "target": 1, "current": 0}], "constraints": ["c"],
    }).json()["id"]
    client.post(f"/mandates/{mandate_id}/activate")

    goal_id = client.post("/goals", json={
        "statement": "Write today's status note", "success_metric": "note exists",
        "budget": {}, "stop_conditions": ["s"],
    }).json()["id"]
    client.post(f"/goals/{goal_id}/activate")

    link_response = client.post(f"/goals/{goal_id}/mandate/{mandate_id}")
    assert link_response.status_code == 200

    report = client.get(f"/mandates/{mandate_id}/report").json()
    assert len(report["workstreams"]) == 1
    assert report["workstreams"][0]["goal_id"] == goal_id


def test_linking_an_unknown_goal_to_a_mandate_is_a_404_not_a_crash():
    client = TestClient(create_app(load_settings()))
    response = client.post("/goals/does-not-exist/mandate/also-does-not-exist")
    assert response.status_code == 404


def test_loop_run_once_plans_and_executes_a_real_workstream_step_through_http():
    """The full plan->claim->execute path, driven entirely through the
    HTTP surface a real deployment would actually use: create a goal,
    activate it, then a single POST /loop/run-once claims and runs it.
    The deterministic test-mode model never returns a valid structured
    plan, so this exercises (and proves) the honest advisory fallback --
    the same safety property test_plan_parsing.py covers in isolation,
    now proven through the real endpoint instead of a unit call."""
    client = TestClient(create_app(load_settings()))

    create_response = client.post("/goals", json={
        "statement": "Say hello",
        "success_metric": "greeted",
        "budget": {},
        "stop_conditions": ["stop if unclear"],
        "review_interval_seconds": 0,
    })
    goal_id = create_response.json()["id"]
    client.post(f"/goals/{goal_id}/activate")

    outcomes = client.post("/loop/run-once").json()

    assert len(outcomes) == 1
    assert outcomes[0]["outcome"] == "advisory"

    goals = client.get("/goals").json()
    assert goals[0]["status"] == "active"  # untouched -- advisory, not a failure
