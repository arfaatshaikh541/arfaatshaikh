from tests.factories import login, make_tenant_with_owner


def test_get_form_config(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    resp = client.get(f"/api/public/{tenant.public_key}/form")
    assert resp.status_code == 200
    body = resp.json()
    assert body["tenant_name"] == tenant.name
    assert any(s["name"] == "External Audit" for s in body["services"])


def test_form_config_unknown_public_key_404(client, db_session):
    import uuid

    resp = client.get(f"/api/public/{uuid.uuid4()}/form")
    assert resp.status_code == 404


def test_form_config_suspended_tenant_404(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    tenant.status = "suspended"
    db_session.commit()
    resp = client.get(f"/api/public/{tenant.public_key}/form")
    assert resp.status_code == 404


def test_submit_creates_lead(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    resp = client.post(
        f"/api/public/{tenant.public_key}/submit",
        json={
            "first_name": "Yousef",
            "last_name": "Hassan",
            "email": "yousef@example-corp.dev",
            "phone": "+971509998888",
            "consent_given": True,
            "utm_source": "google",
            "utm_campaign": "audit-2026",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["reference_number"].startswith("LD-")

    csrf = login(client, owner.email)
    list_resp = client.get(
        "/api/tenants/me/leads",
        params={"search": "yousef@example-corp.dev"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert list_resp.json()["total"] == 1
    lead = list_resp.json()["items"][0]
    assert lead["source"] == "public_form"
    assert lead["utm_source"] == "google"


def test_submit_without_consent_rejected(client, db_session):
    tenant, _owner = make_tenant_with_owner(db_session)
    resp = client.post(
        f"/api/public/{tenant.public_key}/submit",
        json={"first_name": "NoConsent", "consent_given": False},
    )
    assert resp.status_code == 422


def test_submit_honeypot_silently_ignored(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    resp = client.post(
        f"/api/public/{tenant.public_key}/submit",
        json={
            "first_name": "Bot",
            "consent_given": True,
            "website": "http://spam.example",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["reference_number"] is None

    csrf = login(client, owner.email)
    list_resp = client.get(
        "/api/tenants/me/leads",
        params={"search": "Bot"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert list_resp.json()["total"] == 0


def test_submit_required_question_enforced(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    question_id = client.post(
        "/api/tenants/me/qualification-form/questions",
        json={"label": "Company name?", "field_type": "short_text", "is_required": True},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()["id"]

    missing_resp = client.post(
        f"/api/public/{tenant.public_key}/submit",
        json={"first_name": "Missing", "consent_given": True},
    )
    assert missing_resp.status_code == 422

    ok_resp = client.post(
        f"/api/public/{tenant.public_key}/submit",
        json={
            "first_name": "Complete",
            "consent_given": True,
            "answers": [{"question_id": question_id, "value": "Acme LLC"}],
        },
    )
    assert ok_resp.status_code == 200


def test_submit_flags_possible_duplicate(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    payload = {
        "first_name": "Dup",
        "email": "dup@example-corp.dev",
        "consent_given": True,
    }
    first = client.post(f"/api/public/{tenant.public_key}/submit", json=payload)
    assert first.status_code == 200
    second = client.post(f"/api/public/{tenant.public_key}/submit", json=payload)
    assert second.status_code == 200

    csrf = login(client, owner.email)
    list_resp = client.get(
        "/api/tenants/me/leads",
        params={"search": "dup@example-corp.dev"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    items = list_resp.json()["items"]
    assert len(items) == 2
    assert any(item["is_possible_duplicate"] for item in items)


def test_submit_idempotency_key_returns_same_lead(client, db_session):
    tenant, _owner = make_tenant_with_owner(db_session)
    payload = {"first_name": "Idem", "email": "idem@example-corp.dev", "consent_given": True}

    first = client.post(
        f"/api/public/{tenant.public_key}/submit",
        json=payload,
        headers={"Idempotency-Key": "retry-key-1"},
    )
    second = client.post(
        f"/api/public/{tenant.public_key}/submit",
        json=payload,
        headers={"Idempotency-Key": "retry-key-1"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["reference_number"] == second.json()["reference_number"]


def test_submit_idempotency_key_reuse_with_different_payload_conflicts(client, db_session):
    tenant, _owner = make_tenant_with_owner(db_session)
    client.post(
        f"/api/public/{tenant.public_key}/submit",
        json={"first_name": "First", "consent_given": True},
        headers={"Idempotency-Key": "shared-key"},
    )
    conflict = client.post(
        f"/api/public/{tenant.public_key}/submit",
        json={"first_name": "Different", "consent_given": True},
        headers={"Idempotency-Key": "shared-key"},
    )
    assert conflict.status_code == 409


def test_submit_rate_limited_after_many_attempts(client, db_session):
    tenant, _owner = make_tenant_with_owner(db_session)
    for _ in range(20):
        client.post(
            f"/api/public/{tenant.public_key}/submit",
            json={"first_name": "Spammer", "consent_given": True},
        )
    resp = client.post(
        f"/api/public/{tenant.public_key}/submit",
        json={"first_name": "OneTooMany", "consent_given": True},
    )
    assert resp.status_code == 429
