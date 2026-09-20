from __future__ import annotations

from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings


def test_guardian_events_starts_empty():
    client = TestClient(create_app(load_settings()))
    response = client.get("/guardian/events")
    assert response.status_code == 200
    assert response.json() == []


def test_guardian_manual_freeze_engages_kill_switch():
    client = TestClient(create_app(load_settings()))
    response = client.post("/guardian/freeze", json={"reason": "test drill"})
    assert response.status_code == 200
    assert response.json()["action_taken"] == "KILL_SWITCH_ENGAGED"

    status_response = client.post("/kill-switch/disengage")
    assert status_response.json()["kill_switch_engaged"] is False


def test_guardian_autofreezes_after_enough_denials_via_chat():
    client = TestClient(create_app(load_settings()))
    for _ in range(6):
        client.post("/chat", json={"message": "open chrome"})  # denied by policy each time

    events = client.get("/guardian/events").json()
    assert len(events) >= 1
    assert events[0]["rule_name"] == "repeated_denials"


def test_enqueue_and_list_tasks():
    client = TestClient(create_app(load_settings()))
    response = client.post("/tasks", json={"task_type": "send_email", "payload": {"to": "a@b.com"}})
    assert response.status_code == 200
    assert response.json()["status"] == "QUEUED"

    listing = client.get("/tasks").json()
    assert len(listing) == 1
    assert listing[0]["task_type"] == "send_email"

    filtered = client.get("/tasks", params={"status": "QUEUED"}).json()
    assert len(filtered) == 1
