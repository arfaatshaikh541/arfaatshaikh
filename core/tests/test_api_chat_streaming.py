from __future__ import annotations

import json

from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings


def _parse_events(lines: list[str]) -> list[dict]:
    events = []
    for line in lines:
        if not line.startswith("data: "):
            continue
        events.append(json.loads(line[len("data: "):]))
    return events


def test_chat_deterministic_lane_responds_immediately():
    client = TestClient(create_app(load_settings()))

    with client.stream("POST", "/chat", json={"message": "status"}) as response:
        assert response.status_code == 200
        events = _parse_events(list(response.iter_lines()))

    lanes = [e for e in events if e["event"] == "lane"]
    assert lanes[0]["data"] == "deterministic"
    assert any(e["event"] == "done" for e in events)


def test_chat_answers_a_status_question_from_real_mandate_state_not_the_model():
    client = TestClient(create_app(load_settings()))
    client.post("/mandates/run", json={"directive": "Run Gridkeep"})

    with client.stream("POST", "/chat", json={"message": "What's happening with Gridkeep?"}) as response:
        assert response.status_code == 200
        events = _parse_events(list(response.iter_lines()))

    lanes = [e for e in events if e["event"] == "lane"]
    assert lanes[0]["data"] == "mandate_status"

    chunks = [e for e in events if e["event"] == "chunk"]
    full_text = "".join(c["data"] for c in chunks)
    assert "Run Gridkeep" in full_text
    assert "[draft]" in full_text
    assert events[-1]["event"] == "done"


def test_chat_status_question_for_an_unknown_company_is_honest_not_generic():
    client = TestClient(create_app(load_settings()))

    with client.stream("POST", "/chat", json={"message": "Status on Nonexistent Co"}) as response:
        events = _parse_events(list(response.iter_lines()))

    chunks = [e for e in events if e["event"] == "chunk"]
    assert "No mandate found matching 'Nonexistent Co'" in chunks[0]["data"]
    assert events[-1]["data"] == "not_found"


def test_chat_model_lane_streams_multiple_real_chunks():
    # AURA_ENV=test (set by conftest) permits the deterministic test
    # provider fallback since no real Ollama is reachable in this
    # environment — this proves the SSE plumbing genuinely delivers
    # incremental chunks, not that a real model produced them.
    client = TestClient(create_app(load_settings()))

    with client.stream("POST", "/chat", json={"message": "tell me about Gridkeep"}) as response:
        assert response.status_code == 200
        events = _parse_events(list(response.iter_lines()))

    lanes = [e for e in events if e["event"] == "lane"]
    assert lanes[0]["data"] == "model"

    chunks = [e for e in events if e["event"] == "chunk"]
    assert len(chunks) > 1, "expected genuinely incremental streaming, not a single blob"

    full_text = "".join(c["data"] for c in chunks)
    assert "Gridkeep" in full_text

    assert events[-1]["event"] == "done"
