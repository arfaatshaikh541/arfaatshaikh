from __future__ import annotations

from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings


def test_get_capabilities_lists_real_entries_with_availability():
    client = TestClient(create_app(load_settings()))

    response = client.get("/capabilities")

    assert response.status_code == 200
    body = response.json()
    names = {c["name"] for c in body}
    assert "filesystem.read_file" in names
    read_entry = next(c for c in body if c["name"] == "filesystem.read_file")
    assert read_entry["available"] is True


def test_get_capabilities_filters_by_domain():
    client = TestClient(create_app(load_settings()))

    response = client.get("/capabilities", params={"domain": "email"})

    body = response.json()
    assert all(c["domain"] == "email" for c in body)
    assert len(body) > 0


def test_compose_list_and_run_a_skill_through_the_api():
    client = TestClient(create_app(load_settings()))

    compose_response = client.post("/skills", json={
        "name": "write a note", "description": "d", "domain": "files",
        "steps": [{"capability_name": "filesystem.write_file", "params_template": {"path": "note.txt", "content": "hi"}}],
    })
    assert compose_response.status_code == 200, compose_response.text
    skill_id = compose_response.json()["id"]

    listing = client.get("/skills").json()
    assert any(s["id"] == skill_id for s in listing)

    from aura_core.runtime import build_runtime
    build_runtime().policy.set_autonomy_level("filesystem.write_file", 4)

    run_response = client.post(f"/skills/{skill_id}/run", json={"context": {}})
    assert run_response.status_code == 200
    body = run_response.json()
    assert body["status"] == "completed"
    assert body["steps"][0]["status"] == "EXECUTED"


def test_compose_a_skill_with_an_unknown_capability_is_a_400():
    client = TestClient(create_app(load_settings()))

    response = client.post("/skills", json={
        "name": "bad", "description": "d", "domain": "custom",
        "steps": [{"capability_name": "not.a.real.capability"}],
    })

    assert response.status_code == 400


def test_run_an_unknown_skill_is_a_404():
    client = TestClient(create_app(load_settings()))

    response = client.post("/skills/does-not-exist/run", json={"context": {}})

    assert response.status_code == 404


def test_plan_endpoint_reports_an_honest_gap_without_a_real_model():
    client = TestClient(create_app(load_settings()))

    response = client.post("/plan", json={"objective": "do something nobody defined a capability for"})

    assert response.status_code == 200
    body = response.json()
    assert body["fully_resolved"] is False
    assert len(body["gaps"]) == 1
