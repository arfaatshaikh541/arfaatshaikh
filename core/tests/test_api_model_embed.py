from __future__ import annotations

from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings


def test_embed_returns_a_real_vector():
    client = TestClient(create_app(load_settings()))

    response = client.post("/model/embed", json={"text": "hello world"})

    assert response.status_code == 200
    body = response.json()
    assert body["dimensions"] == 8
    assert len(body["embedding"]) == 8


def test_embed_is_gated_once_enrolled():
    app = create_app(load_settings())
    app.state.runtime.enrollment.enroll_owner("Ada")
    client = TestClient(app)

    response = client.post("/model/embed", json={"text": "hello"})

    assert response.status_code == 401
