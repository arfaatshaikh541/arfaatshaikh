from __future__ import annotations

from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings


def test_memory_search_endpoint_ranks_real_records():
    client = TestClient(create_app(load_settings()))
    client.app.state.runtime.memory.record_event(
        event_type="pricing", summary="Gridkeep customers moved to tiered pricing", source="s",
    )
    client.app.state.runtime.memory.record_event(
        event_type="weather", summary="It rained today", source="s",
    )

    response = client.get("/memory/search", params={"q": "Gridkeep pricing"})

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert "Gridkeep" in results[0]["text"]


def test_memory_ask_endpoint_answers_from_real_context():
    client = TestClient(create_app(load_settings()))
    client.app.state.runtime.memory.record_decision(
        goal="pricing", statement="Charge Gridkeep customers a flat monthly fee",
        reasoning="simplest to bill", source="s",
    )

    response = client.post("/memory/ask", json={"question": "Why did we decide to charge Gridkeep that way?"})

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["answer"] is not None
    assert len(body["context_used"]) >= 1


def test_memory_ask_with_nothing_relevant_reports_an_honest_error():
    client = TestClient(create_app(load_settings()))
    response = client.post("/memory/ask", json={"question": "What happened with the flying saucers?"})

    assert response.status_code == 200
    body = response.json()
    assert body["error"] == "no relevant memory found for this question"
    assert body["answer"] is None
