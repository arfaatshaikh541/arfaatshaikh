"""End-to-end API tests against a real PostgreSQL database that has been migrated to head.

Skipped unless WOI_TEST_DATABASE_URL is set (an EMPTY, migrated database; the tests write to it):

    WOI_TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/woi_test uv run pytest tests/integration -q
"""
import os
import uuid

import pytest
import pytest_asyncio

TEST_DB = os.environ.get("WOI_TEST_DATABASE_URL")
# One event loop for the whole module: the application's database engine is created once and must not outlive its loop.
pytestmark = [pytest.mark.skipif(not TEST_DB, reason="WOI_TEST_DATABASE_URL not set"), pytest.mark.asyncio(loop_scope="module")]

if TEST_DB:
    os.environ["WOI_DATABASE_URL"] = TEST_DB

PASSWORD = "Str0ng-Passw0rd-xyz!"


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def app_client():
    """An anonymous client (no cookies) - signed-in users get their own client from make_user()."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def make_user(_anonymous, admin: bool = False):
    """Returns (client with its own cookie jar, csrf headers, user id)."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    email = f"it-{uuid.uuid4().hex[:10]}@example.org"
    r = await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD, "display_name": "IT"})
    assert r.status_code == 201, r.text
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    csrf = r.json()["csrf_token"]
    user_id = r.json()["user"]["id"]
    if admin:
        from sqlalchemy import text
        from app.core.config import get_settings
        from app.db.session import Database
        db = Database(get_settings())
        async with db.session_factory() as session:
            await session.execute(text("insert into platform_administrators (id, user_id, active, reason, created_at, updated_at) values (gen_random_uuid(), :u, true, 'integration test', now(), now())"), {"u": user_id})
            await session.commit()
        await db.dispose()
    return client, {"X-CSRF-Token": csrf}, user_id


async def test_public_endpoints_work_on_an_empty_database(app_client):
    for path in ("/api/v1/knowledge/readiness", "/api/v1/knowledge/records", "/api/v1/directory/listings", "/api/v1/directory/summary",
                 "/api/v1/knowledge/graph/stats", "/api/v1/knowledge/manifest", "/api/v1/search?q=patience"):
        r = await app_client.get(path)
        assert r.status_code == 200, (path, r.text)
    assert (await app_client.get("/api/v1/directory/listings/00000000-0000-0000-0000-000000000000")).status_code == 404
    summary = (await app_client.get("/api/v1/directory/summary")).json()["types"]
    assert all(item["count"] == 0 for item in summary) and len(summary) == 9


async def test_admin_endpoints_require_authentication_and_admin_role(app_client):
    for method, path in (("get", "/api/v1/admin/datasets"), ("get", "/api/v1/admin/datasets/audit/events"), ("get", "/api/v1/directory/admin/queue"), ("get", "/api/v1/assistant/admin/runs")):
        assert (await getattr(app_client, method)(path)).status_code == 401
    client, headers, _ = await make_user(app_client)
    assert (await client.get("/api/v1/admin/datasets")).status_code == 403
    assert (await client.post("/api/v1/admin/datasets/manifest/sync", headers=headers)).status_code == 403


async def test_mutations_without_csrf_are_rejected(app_client):
    client, _, _ = await make_user(app_client, admin=True)
    assert (await client.post("/api/v1/admin/datasets/manifest/sync")).status_code == 403


async def test_dataset_lifecycle_publication_gate_import_rollback_and_audit(app_client):
    from sqlalchemy import text
    from app.core.config import get_settings
    from app.db.session import Database
    db = Database(get_settings())
    async with db.session_factory() as session:  # start from a clean slate so the test can be re-run
        await session.execute(text("delete from data_sets where dataset_key = 'seerah'"))
        await session.commit()
    await db.dispose()
    admin, headers, _ = await make_user(app_client, admin=True)
    r = await admin.post("/api/v1/admin/datasets/manifest/sync", headers=headers)
    assert r.status_code == 200 and r.json()["applied"], r.text
    seerah = next(d for d in (await admin.get("/api/v1/admin/datasets")).json()["datasets"] if d["id"] == "seerah")
    assert seerah["publication_status"] == "staged" and not seerah["can_publish"]

    r = await admin.post("/api/v1/admin/datasets/seerah/action", headers=headers, json={"action": "publish"})
    assert r.status_code == 409 and r.json()["error"]["details"]["reasons"]

    record = {"id": "seerah-0001", "entity_type": "seerah", "title": "Owner supplied example", "description": "A record supplied by the owner for this test.",
              "source": "Owner dataset (test)", "license": "Owner permission", "provenance": "Supplied by the test suite; not real religious content."}
    upload = {"records": [record, {**record, "title": ""}, {"nonsense": True}]}
    r = await admin.post("/api/v1/admin/datasets/seerah/import", headers=headers, json=upload)
    body = r.json()
    assert r.status_code == 200 and (body["created"], body["failed"]) == (1, 2) and len(body["failures"]) == 2
    first_import = body["id"]
    assert (await admin.post("/api/v1/admin/datasets/seerah/import", headers=headers, json=upload)).json()["id"] == first_import  # idempotent

    # an import never verifies itself; publication stays blocked until a person verifies AND rights are confirmed
    r = await admin.post("/api/v1/admin/datasets/seerah/action", headers=headers, json={"action": "publish", "confirmed_by": "Owner", "confirmed_on": "2026-10-01", "basis": "written permission (test)"})
    assert r.status_code == 409 and any("validation" in x for x in r.json()["error"]["details"]["reasons"])
    assert (await admin.post("/api/v1/admin/datasets/seerah/action", headers=headers, json={"action": "mark_verified"})).status_code == 422  # note required
    assert (await admin.post("/api/v1/admin/datasets/seerah/action", headers=headers, json={"action": "mark_verified", "note": "Checked the failure report and the record by hand."})).status_code == 200

    assert (await app_client.get("/api/v1/knowledge/records?type=seerah")).json()["total"] == 0  # still hidden
    assert (await app_client.get("/api/v1/search?q=Owner&types=seerah")).json()["results"] == []

    r = await admin.post("/api/v1/admin/datasets/seerah/action", headers=headers, json={"action": "publish", "confirmed_by": "Owner", "confirmed_on": "2026-10-01", "basis": "written permission (test)"})
    assert r.status_code == 200 and r.json()["publication_status"] == "published" and r.json()["license"]["status"] == "OWNER_PERMISSION_GRANTED"
    public = (await app_client.get("/api/v1/knowledge/records?type=seerah")).json()
    assert public["total"] == 1 and public["items"][0]["provenance"] and public["items"][0]["source"] == "Owner dataset (test)"
    assert (await app_client.get("/api/v1/search?q=Owner&types=seerah")).json()["results"][0]["type"] == "seerah"

    # disabling hides it again; rollback removes what the import created
    await admin.post("/api/v1/admin/datasets/seerah/action", headers=headers, json={"action": "disable"})
    assert (await app_client.get("/api/v1/knowledge/records?type=seerah")).json()["total"] == 0
    await admin.post("/api/v1/admin/datasets/seerah/action", headers=headers, json={"action": "enable"})
    r = await admin.post(f"/api/v1/admin/datasets/imports/{first_import}/rollback", headers=headers)
    assert r.status_code == 200 and r.json()["status"] == "rolled_back"
    assert (await app_client.get("/api/v1/knowledge/records?type=seerah")).json()["total"] == 0

    actions = {e["action"] for e in (await admin.get("/api/v1/admin/datasets/audit/events?limit=200")).json()["events"]}
    assert {"dataset.manifest_synced", "dataset.import", "dataset.publish", "dataset.disable", "dataset.import_rolled_back", "dataset.mark_verified"} <= actions


async def test_directory_suggest_moderate_report_and_search(app_client):
    admin, admin_headers, _ = await make_user(app_client, admin=True)
    user, user_headers, _ = await make_user(app_client)
    unique = uuid.uuid4().hex[:8]
    payload = {"listing_type": "mosque", "name": f"Test Community Masjid {unique}", "city": "Leeds", "country": "GB", "latitude": 53.8008, "longitude": -1.5491,
               "source": "Community suggestion", "license": "Contributor grant", "provenance": "Suggested by a signed-in user (test)"}
    r = await user.post("/api/v1/directory/listings", headers=user_headers, json=payload)
    assert r.status_code == 201 and r.json()["status"] == "pending"
    listing_id = r.json()["id"]
    assert (await app_client.get(f"/api/v1/directory/listings/{listing_id}")).status_code == 404  # not public until approved
    # duplicate suggestion is linked, not published twice
    r2 = await user.post("/api/v1/directory/listings", headers=user_headers, json={**payload, "name": f"The Test Community Masjid {unique}"})
    assert r2.status_code == 201

    queue = (await admin.get("/api/v1/directory/admin/queue")).json()["items"]
    assert any(item["id"] == listing_id for item in queue)
    r = await admin.post(f"/api/v1/directory/admin/listings/{listing_id}/moderate", headers=admin_headers, json={"action": "approve"})
    assert r.status_code == 200 and r.json()["status"] == "published"
    assert (await admin.post(f"/api/v1/directory/admin/listings/{listing_id}/moderate", headers=admin_headers, json={"action": "verify"})).json()["verification_status"] == "verified"

    found = (await app_client.get(f"/api/v1/directory/listings?q={unique}&lat=53.8&lon=-1.55&radius_km=5&verified_only=true")).json()
    assert found["items"] and found["items"][0]["distance_km"] is not None and found["items"][0]["source"] == "Community suggestion"
    assert (await app_client.get(f"/api/v1/directory/listings?q={unique}&lat=10&lon=10&radius_km=5")).json()["items"] == []
    assert (await app_client.get(f"/api/v1/search?q={unique}&types=directory")).json()["results"][0]["type"] == "directory"

    r = await user.post(f"/api/v1/directory/listings/{listing_id}/report", headers=user_headers, json={"reason": "closed", "details": "test"})
    assert r.status_code == 201
    reports = (await admin.get("/api/v1/directory/admin/reports")).json()["items"]
    assert reports
    r = await admin.post(f"/api/v1/directory/admin/reports/{reports[0]['id']}/resolve", headers=admin_headers, json={"outcome": "actioned", "hide_listing": True, "note": "closed"})
    assert r.status_code == 200
    assert (await app_client.get(f"/api/v1/directory/listings/{listing_id}")).status_code == 404

    events = (await admin.get("/api/v1/admin/datasets/audit/events?action=directory")).json()["events"]
    assert {e["action"] for e in events} >= {"directory.approve", "directory.verify", "directory.report_actioned"}


async def test_invalid_input_is_rejected(app_client):
    client, headers, _ = await make_user(app_client)
    bad = {"listing_type": "shop", "name": "x", "source": "s", "license": "l", "provenance": "p"}
    assert (await client.post("/api/v1/directory/listings", headers=headers, json=bad)).status_code == 422
    assert (await app_client.get("/api/v1/directory/listings?lat=95&lon=0")).status_code == 422
    assert (await app_client.get("/api/v1/knowledge/records?type=made_up")).status_code == 422
    assert (await app_client.get("/api/v1/search?q=a")).status_code == 422


async def test_assistant_abstains_when_there_is_no_evidence(app_client):
    client, headers, _ = await make_user(app_client)
    r = await client.post("/api/v1/assistant/query", headers=headers, json={"question": "What does the Qur'an say about patience?"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "insufficient" and body["message"] == "Insufficient verified sources."
    assert body["evidence"] == [] and body["claims"] == [] and body["ai_synthesis"]["text"] is None
    assert body["confidence"]["abstained"] is True


class _StubProvider:
    def __init__(self, text, available=True):
        self.text, self.available = text, available

    async def generate(self, prompt):
        from app.services.ai_provider import AIGenerationResult
        return AIGenerationResult(available=self.available, provider="stub", text=self.text if self.available else None, error=None if self.available else "down")


def _fixture_evidence():
    from app.services.retrieval import EvidenceContract, sha256_text
    texts = [("quran", "eng-x:94:6", "Lo! with hardship goeth ease", "Pickthall"), ("quran", "eng-x:2:153", "Seek help in patience and prayer; truly Allah is with the patient", "Pickthall")]
    return [EvidenceContract(chunk_id=str(uuid.uuid4()), document_id=str(uuid.uuid4()), corpus_type=c, canonical_reference=r, source_edition_id="e", source_passage_id=f"p-{r}",
                             exact_text=t, text_sha256=sha256_text(t), attribution=a, licence="Public domain") for c, r, t, a in texts]


async def _ask(app_client, monkeypatch, provider, include=True):
    from app.api.routes import assistant as route
    evidence = _fixture_evidence()

    async def fake_search(db, corpora, question, limit):
        return evidence
    monkeypatch.setattr(route, "search_evidence", fake_search)
    monkeypatch.setattr(route, "get_ai_provider", lambda settings: provider)
    client, headers, _ = await make_user(app_client)
    r = await client.post("/api/v1/assistant/query", headers=headers, json={"question": "What does the Qur'an say about patience in hardship?", "include_synthesis": include})
    assert r.status_code == 200, r.text
    return r.json()


async def test_assistant_sections_and_validated_synthesis(app_client, monkeypatch):
    body = await _ask(app_client, monkeypatch, _StubProvider("Patience is described as a means of help [1]. Hardship is described as accompanied by ease [2]."))
    assert body["status"] == "assembled" and body["confidence"]["abstained"] is False
    assert len(body["sections"]["primary_source"]) == 2 and body["sections"]["scholarly_explanation"] == []
    assert body["ai_synthesis"]["status"] == "validated" and body["ai_synthesis"]["label"] == "AI SYNTHESIS"


async def test_synthesis_with_fabricated_citation_is_rejected_not_shown(app_client, monkeypatch):
    body = await _ask(app_client, monkeypatch, _StubProvider("Patience is rewarded in the hereafter [7]."))
    assert body["ai_synthesis"]["status"] == "rejected" and body["ai_synthesis"]["text"] is None
    assert body["sections"]["primary_source"]  # the verified sources are still shown


async def test_synthesis_is_unavailable_when_no_local_model(app_client, monkeypatch):
    body = await _ask(app_client, monkeypatch, _StubProvider(None, available=False))
    assert body["ai_synthesis"]["status"] == "unavailable" and body["ai_synthesis"]["text"] is None


async def test_synthesis_not_requested_by_default(app_client, monkeypatch):
    body = await _ask(app_client, monkeypatch, _StubProvider("never called"), include=False)
    assert body["ai_synthesis"]["status"] == "not_requested"


async def test_admin_can_review_which_sources_an_answer_cited(app_client, monkeypatch):
    await _ask(app_client, monkeypatch, _StubProvider("Patience helps [1]."))
    admin, _, _ = await make_user(app_client, admin=True)
    runs = (await admin.get("/api/v1/assistant/admin/runs?limit=5")).json()["runs"]
    assert runs and runs[0]["status"] in {"assembled", "insufficient"}
