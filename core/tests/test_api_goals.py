from __future__ import annotations

from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings


def test_create_activate_and_review_a_goal_through_the_api():
    client = TestClient(create_app(load_settings()))

    create_response = client.post("/goals", json={
        "statement": "Grow Gridkeep revenue",
        "success_metric": "MRR >= 100000 AED",
        "budget": {"marketing_aed_per_month": 5000},
        "stop_conditions": ["pause if CAC too high"],
        "review_interval_seconds": 0,
    })
    assert create_response.status_code == 200
    goal_id = create_response.json()["id"]
    assert create_response.json()["status"] == "draft"

    activate_response = client.post(f"/goals/{goal_id}/activate")
    assert activate_response.json()["status"] == "active"

    listing = client.get("/goals").json()
    assert len(listing) == 1
    assert listing[0]["id"] == goal_id

    review_response = client.post("/goals/review")
    outcomes = review_response.json()
    assert len(outcomes) == 1
    assert outcomes[0]["goal_id"] == goal_id
    assert outcomes[0]["error"] is None
    assert outcomes[0]["task_id"] is not None

    tasks = client.get("/tasks").json()
    assert any(t["task_type"] == "execute_goal_step" for t in tasks)


def test_activate_without_required_fields_returns_an_error():
    client = TestClient(create_app(load_settings()))
    create_response = client.post("/goals", json={"statement": "Underspecified goal"})
    goal_id = create_response.json()["id"]

    activate_response = client.post(f"/goals/{goal_id}/activate")
    assert "error" in activate_response.json()
