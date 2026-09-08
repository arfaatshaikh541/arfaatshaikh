from __future__ import annotations

from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings


def test_record_list_and_resolve_an_opportunity_through_the_api():
    client = TestClient(create_app(load_settings()))

    record_response = client.post("/opportunities", json={
        "category": "upsell", "summary": "Customer X tripled usage",
        "evidence": "usage logs", "confidence": 0.8, "estimated_impact": "high",
    })
    assert record_response.status_code == 200
    opportunity_id = record_response.json()["id"]

    listing = client.get("/opportunities").json()
    assert any(o["id"] == opportunity_id for o in listing)

    resolve_response = client.post(f"/opportunities/{opportunity_id}/status", params={"status": "acted_on"})
    assert resolve_response.status_code == 200

    listing_after = client.get("/opportunities").json()
    assert not any(o["id"] == opportunity_id for o in listing_after)


def test_setting_status_on_an_unknown_opportunity_is_a_404():
    client = TestClient(create_app(load_settings()))

    response = client.post("/opportunities/does-not-exist/status", params={"status": "dismissed"})

    assert response.status_code == 404
