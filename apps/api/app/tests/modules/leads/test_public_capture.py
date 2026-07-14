from app.tests.factories import create_capture_token, create_tenant_with_owner


def test_public_capture_happy_path_creates_lead_and_follow_up_task(client, db_session, fake_email):
    tenant, _owner = create_tenant_with_owner(db_session)
    token = create_capture_token(db_session, tenant.id)

    services = client.get(f"/api/public/capture/{token}/services").json()["services"]
    service_id = services[0]["id"]

    response = client.post(
        f"/api/public/capture/{token}/enquiry",
        json={
            "first_name": "Ahmed", "last_name": "Khalid", "email": "ahmed@testclient.internal",
            "phone": "+971500000000", "company": "Khalid LLC", "service_id": service_id,
            "consent_given": True, "utm_source": "google",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "received"
    assert body["reference_number"]
    assert any(m["to"] == "ahmed@testclient.internal" for m in fake_email.sent)  # acknowledgement email was sent


def test_public_capture_rejects_unknown_token(client, db_session):
    response = client.post("/api/public/capture/does-not-exist/enquiry", json={"first_name": "X"})
    assert response.status_code == 404


def test_public_capture_honeypot_silently_drops(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session)
    token = create_capture_token(db_session, tenant.id)

    response = client.post(
        f"/api/public/capture/{token}/enquiry",
        json={"first_name": "Bot", "last_name": "Spam", "email": "bot@spam.internal", "website": "http://spam.example"},
    )

    assert response.status_code == 201
    assert response.json() == {"status": "received"}

    # Nothing was actually persisted — verified via the tenant-side API.
    from app.tests.conftest import login

    login(client, "owner@test.internal", "OwnerPass!2345")
    leads = client.get("/api/tenant/leads").json()["items"]
    assert not any(lead["email"] == "bot@spam.internal" for lead in leads)


def test_public_capture_idempotency_key_returns_same_lead(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session)
    token = create_capture_token(db_session, tenant.id)

    payload = {"first_name": "Sara", "last_name": "Ali", "email": "sara@testclient.internal", "idempotency_key": "req-123"}
    first = client.post(f"/api/public/capture/{token}/enquiry", json=payload)
    second = client.post(f"/api/public/capture/{token}/enquiry", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["reference_number"] == second.json()["reference_number"]


def test_public_capture_flags_duplicate_by_email(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session)
    token = create_capture_token(db_session, tenant.id)

    client.post(f"/api/public/capture/{token}/enquiry", json={"first_name": "Omar", "last_name": "Said", "email": "omar@testclient.internal"})
    response = client.post(f"/api/public/capture/{token}/enquiry", json={"first_name": "Omar", "last_name": "Said2", "email": "omar@testclient.internal"})

    assert response.status_code == 201

    from app.tests.conftest import login

    login(client, "owner@test.internal", "OwnerPass!2345")
    leads = client.get("/api/tenant/leads").json()["items"]
    matching = [lead for lead in leads if lead["email"] == "omar@testclient.internal"]
    assert len(matching) == 2
    assert any(lead["is_possible_duplicate"] for lead in matching)
    assert any(not lead["is_possible_duplicate"] for lead in matching)


def test_public_capture_throttled_after_repeated_submissions(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session)
    token = create_capture_token(db_session, tenant.id)

    for i in range(10):
        client.post(f"/api/public/capture/{token}/enquiry", json={"first_name": f"Lead{i}", "email": f"lead{i}@testclient.internal"})

    response = client.post(f"/api/public/capture/{token}/enquiry", json={"first_name": "Overflow", "email": "overflow@testclient.internal"})

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "capture_rate_limited"


def test_public_capture_rejected_when_lead_capture_module_disabled(client, db_session):
    from app.modules.entitlements.service import grant_feature_override

    tenant, _owner = create_tenant_with_owner(db_session, plan_code="starter")
    token = create_capture_token(db_session, tenant.id)
    grant_feature_override(db_session, tenant_id=tenant.id, feature_code="lead_capture", config={"enabled": False}, granted_by=None)
    db_session.commit()

    response = client.post(f"/api/public/capture/{token}/enquiry", json={"first_name": "Blocked", "email": "blocked@testclient.internal"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "module_not_enabled"
