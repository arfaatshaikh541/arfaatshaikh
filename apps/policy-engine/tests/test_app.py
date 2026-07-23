from fastapi.testclient import TestClient

from policy_engine.app import create_app


def client() -> TestClient:
    return TestClient(create_app())


def test_evaluate_endpoint_allows() -> None:
    response = client().post(
        "/evaluate",
        json={
            "policy_id": "p1",
            "policy_version": 1,
            "policy": {"residency": {"allowed_countries": ["AE"]}},
            "candidate": {
                "country": "AE",
                "operator_id": "op_gulf_horizon",
                "confidential_computing_available": True,
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "allow"
    assert body["reason_codes"] == []
    assert body["policy_id"] == "p1"
    assert body["policy_version"] == 1
    assert "inputs_hash" in body


def test_evaluate_endpoint_denies_with_reason_codes() -> None:
    response = client().post(
        "/evaluate",
        json={
            "policy_id": "p1",
            "policy_version": 1,
            "policy": {"residency": {"denied_countries": ["AE"]}},
            "candidate": {
                "country": "AE",
                "operator_id": "op_gulf_horizon",
                "confidential_computing_available": True,
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "deny"
    assert "RESIDENCY_DENIED_COUNTRY" in body["reason_codes"]


def test_evaluate_endpoint_rejects_malformed_request() -> None:
    response = client().post("/evaluate", json={"policy_id": "p1"})
    assert response.status_code == 422


def test_conflicts_endpoint_reports_no_conflict() -> None:
    response = client().post(
        "/conflicts",
        json={
            "policy_a_id": "a",
            "policy_a": {},
            "policy_b_id": "b",
            "policy_b": {},
        },
    )
    assert response.status_code == 200
    assert response.json() == {"has_conflicts": False, "conflicts": []}


def test_conflicts_endpoint_reports_a_conflict() -> None:
    response = client().post(
        "/conflicts",
        json={
            "policy_a_id": "a",
            "policy_a": {"residency": {"allowed_countries": ["AE"]}},
            "policy_b_id": "b",
            "policy_b": {"residency": {"allowed_countries": ["DE"]}},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["has_conflicts"] is True
    assert len(body["conflicts"]) == 1
