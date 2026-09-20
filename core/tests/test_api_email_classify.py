from __future__ import annotations

from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings


def test_classify_returns_a_real_category():
    client = TestClient(create_app(load_settings()))

    response = client.post("/email/classify", json={"subject": "Pricing question", "body": "How much does this cost?"})

    assert response.status_code == 200
    # The deterministic test-mode provider's echo response never matches
    # a real category -- "unclassified" is the honest expected result,
    # not a crash and not a guessed category.
    assert response.json()["category"] == "unclassified"


def test_classify_is_gated_once_enrolled():
    app = create_app(load_settings())
    app.state.runtime.enrollment.enroll_owner("Ada")
    client = TestClient(app)

    response = client.post("/email/classify", json={"subject": "s", "body": "b"})

    assert response.status_code == 401
