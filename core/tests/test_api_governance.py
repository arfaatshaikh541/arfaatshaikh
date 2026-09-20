from __future__ import annotations

import json

from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings


def _parse_events(lines: list[str]) -> list[dict]:
    events = []
    for line in lines:
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: "):]))
    return events


def test_open_chrome_is_denied_by_policy_not_silently_executed():
    client = TestClient(create_app(load_settings()))
    with client.stream("POST", "/chat", json={"message": "open chrome"}) as response:
        events = _parse_events(list(response.iter_lines()))

    done = [e for e in events if e["event"] == "done"][0]
    assert done["data"] == "DENIED"


def test_audit_log_is_populated_and_verifiable_after_actions():
    client = TestClient(create_app(load_settings()))
    client.post("/chat", json={"message": "status"})

    audit_response = client.get("/audit")
    assert audit_response.status_code == 200
    assert len(audit_response.json()) >= 1

    verify_response = client.get("/audit/verify")
    assert verify_response.json()["valid"] is True


def test_kill_switch_blocks_chat_actions_until_disengaged():
    client = TestClient(create_app(load_settings()))

    client.post("/kill-switch/engage")
    with client.stream("POST", "/chat", json={"message": "status"}) as response:
        events = _parse_events(list(response.iter_lines()))
    done = [e for e in events if e["event"] == "done"][0]
    assert done["data"] == "KILL_SWITCH_ENGAGED"

    client.post("/kill-switch/disengage")
    with client.stream("POST", "/chat", json={"message": "status"}) as response:
        events = _parse_events(list(response.iter_lines()))
    done = [e for e in events if e["event"] == "done"][0]
    assert done["data"] == "EXECUTED"


def test_approvals_list_starts_empty():
    client = TestClient(create_app(load_settings()))
    response = client.get("/approvals")
    assert response.status_code == 200
    assert response.json() == []
