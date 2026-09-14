from uuid import UUID

from fastapi.testclient import TestClient

from app.main import app


def test_request_id_is_generated_and_returned() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    UUID(response.headers["X-Request-ID"])


def test_valid_request_id_is_preserved() -> None:
    request_id = "018f7d89-4d83-7a6a-a6ea-89d2ddb06ce8"
    with TestClient(app) as client:
        response = client.get("/health/live", headers={"X-Request-ID": request_id})

    assert response.headers["X-Request-ID"] == request_id


def test_invalid_request_id_is_replaced() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live", headers={"X-Request-ID": "not-a-uuid"})

    returned = response.headers["X-Request-ID"]
    assert returned != "not-a-uuid"
    UUID(returned)
