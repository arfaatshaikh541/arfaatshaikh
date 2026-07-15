from app.tests.conftest import login
from app.tests.factories import add_member, create_tenant_with_owner


def _create_lead(client, **overrides) -> dict:
    payload = {"first_name": "Client", "last_name": "One", "email": "client.one@testclient.internal"}
    payload.update(overrides)
    response = client.post("/api/tenant/leads", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _create_request(client, lead_id: str, **overrides) -> dict:
    payload = {"lead_id": lead_id, "title": "Passport copy", "description": "A clear scan of your passport."}
    payload.update(overrides)
    response = client.post("/api/tenant/document-requests", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _seed_email_template(client, trigger_event: str, name: str):
    response = client.post(
        "/api/tenant/communications/templates",
        json={
            "name": name, "trigger_event": trigger_event, "subject": f"{name}: {{{{document_title}}}}",
            "body_text": f"{name} for {{{{document_title}}}}.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_document_request_and_staff_upload(client, db_session, fake_email):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")
    _seed_email_template(client, "document_requested", "Document Requested")

    lead = _create_lead(client)
    request = _create_request(client, lead["id"])
    assert request["status"] == "requested"
    assert request["public_token"]
    assert any(m["to"] == "client.one@testclient.internal" for m in fake_email.sent)

    upload = client.post(
        f"/api/tenant/document-requests/{request['id']}/documents",
        files={"file": ("passport.pdf", b"%PDF-1.4 fake passport content", "application/pdf")},
    )
    assert upload.status_code == 201, upload.text

    detail = client.get(f"/api/tenant/document-requests/{request['id']}").json()
    assert detail["status"] == "uploaded"

    documents = client.get(f"/api/tenant/document-requests/{request['id']}/documents").json()
    assert len(documents) == 1
    assert documents[0]["file_name"] == "passport.pdf"

    download = client.get(f"/api/tenant/document-requests/{request['id']}/documents/{documents[0]['id']}/download-url")
    assert download.status_code == 200
    assert download.json()["url"]


def test_approve_document_request_notifies_client(client, db_session, fake_email):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")
    _seed_email_template(client, "document_approved", "Document Approved")

    lead = _create_lead(client)
    request = _create_request(client, lead["id"])
    client.post(
        f"/api/tenant/document-requests/{request['id']}/documents",
        files={"file": ("passport.pdf", b"fake content", "application/pdf")},
    )

    approve = client.post(f"/api/tenant/document-requests/{request['id']}/approve", json={"notes": "Looks good"})
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"
    assert approve.json()["review_notes"] == "Looks good"

    assert any(m["to"] == "client.one@testclient.internal" and "Approved" in m["subject"] for m in fake_email.sent)


def test_reject_document_request_records_notes(client, db_session):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")

    lead = _create_lead(client)
    request = _create_request(client, lead["id"])
    client.post(
        f"/api/tenant/document-requests/{request['id']}/documents",
        files={"file": ("passport.pdf", b"fake content", "application/pdf")},
    )

    reject = client.post(f"/api/tenant/document-requests/{request['id']}/reject", json={"notes": "Blurry scan"})
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"
    assert reject.json()["review_notes"] == "Blurry scan"

    cannot_approve_twice = client.post(f"/api/tenant/document-requests/{request['id']}/approve", json={"notes": ""})
    assert cannot_approve_twice.status_code == 422
    assert cannot_approve_twice.json()["error"]["code"] == "document_not_uploaded"


def test_disallowed_content_type_is_rejected(client, db_session):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")

    lead = _create_lead(client)
    request = _create_request(client, lead["id"])

    upload = client.post(
        f"/api/tenant/document-requests/{request['id']}/documents",
        files={"file": ("archive.zip", b"PK\x03\x04 fake zip", "application/zip")},
    )
    assert upload.status_code == 403
    assert upload.json()["error"]["code"] == "document_type_not_allowed"


def test_malware_signature_is_flagged(client, db_session):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")

    lead = _create_lead(client)
    request = _create_request(client, lead["id"])

    eicar = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    upload = client.post(
        f"/api/tenant/document-requests/{request['id']}/documents",
        files={"file": ("test.pdf", eicar, "application/pdf")},
    )
    assert upload.status_code == 403
    assert upload.json()["error"]["code"] == "malware_detected"


def test_storage_usage_limit_blocks_upload(client, db_session):
    from app.modules.entitlements.service import grant_feature_override

    tenant, _owner = create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")

    lead = _create_lead(client)
    request = _create_request(client, lead["id"])

    grant_feature_override(db_session, tenant_id=tenant.id, feature_code="document_storage_mb", config={"limit": 0}, granted_by=None)
    db_session.commit()

    upload = client.post(
        f"/api/tenant/document-requests/{request['id']}/documents",
        files={"file": ("passport.pdf", b"fake content", "application/pdf")},
    )
    assert upload.status_code == 403
    assert upload.json()["error"]["code"] == "usage_limit_exceeded"


def test_public_view_and_upload(client, db_session):
    create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")

    lead = _create_lead(client)
    request = _create_request(client, lead["id"], notify=False)
    client.post("/api/auth/logout")

    public_view = client.get(f"/api/public/documents/{request['public_token']}")
    assert public_view.status_code == 200
    assert public_view.json()["title"] == "Passport copy"

    public_upload = client.post(
        f"/api/public/documents/{request['public_token']}/upload",
        files={"file": ("passport.pdf", b"fake content", "application/pdf")},
    )
    assert public_upload.status_code == 201, public_upload.text

    login(client, "owner@test.internal", "OwnerPass!2345")
    detail = client.get(f"/api/tenant/document-requests/{request['id']}").json()
    assert detail["status"] == "uploaded"
    documents = client.get(f"/api/tenant/document-requests/{request['id']}/documents").json()
    assert documents[0]["uploaded_by"] is None  # public upload — no staff attribution


def test_public_upload_blocked_when_module_disabled(client, db_session):
    from app.modules.entitlements.service import grant_feature_override

    tenant, _owner = create_tenant_with_owner(db_session, plan_code="professional")
    login(client, "owner@test.internal", "OwnerPass!2345")

    lead = _create_lead(client)
    request = _create_request(client, lead["id"], notify=False)

    grant_feature_override(db_session, tenant_id=tenant.id, feature_code="document_collection", config={"enabled": False}, granted_by=None)
    db_session.commit()
    client.post("/api/auth/logout")

    # Unlike the public proposal accept/reject routes, uploads ARE gated:
    # accepting/rejecting a proposal just flips a flag, but uploading a
    # file consumes ongoing storage a lapsed subscription shouldn't get.
    public_view = client.get(f"/api/public/documents/{request['public_token']}")
    assert public_view.status_code == 200  # viewing what's requested still works

    public_upload = client.post(
        f"/api/public/documents/{request['public_token']}/upload",
        files={"file": ("passport.pdf", b"fake content", "application/pdf")},
    )
    assert public_upload.status_code == 403
    assert public_upload.json()["error"]["code"] == "module_not_enabled"


def test_sales_agent_can_upload_but_not_approve(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session, plan_code="professional")
    add_member(db_session, tenant=tenant, email="agent@test.internal", password="AgentPass!2345", role_name="Sales Agent")

    login(client, "owner@test.internal", "OwnerPass!2345")
    lead = _create_lead(client)
    request = _create_request(client, lead["id"])
    client.post("/api/auth/logout")

    login(client, "agent@test.internal", "AgentPass!2345")
    upload = client.post(
        f"/api/tenant/document-requests/{request['id']}/documents",
        files={"file": ("passport.pdf", b"fake content", "application/pdf")},
    )
    assert upload.status_code == 201

    approve = client.post(f"/api/tenant/document-requests/{request['id']}/approve", json={"notes": ""})
    assert approve.status_code == 403
    assert approve.json()["error"]["code"] == "permission_denied"


def test_document_requests_are_isolated_between_tenants(client, db_session):
    create_tenant_with_owner(db_session, name="Tenant A", owner_email="ownera@test.internal", plan_code="professional")
    create_tenant_with_owner(db_session, name="Tenant B", owner_email="ownerb@test.internal", plan_code="professional")

    login(client, "ownera@test.internal", "OwnerPass!2345")
    lead = _create_lead(client)
    _create_request(client, lead["id"])
    client.post("/api/auth/logout")

    login(client, "ownerb@test.internal", "OwnerPass!2345")
    requests = client.get("/api/tenant/document-requests").json()
    assert requests == []
