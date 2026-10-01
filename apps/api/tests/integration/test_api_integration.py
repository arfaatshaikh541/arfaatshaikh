"""End-to-end API tests against a real PostgreSQL database that has been migrated to head.

Skipped unless WOI_TEST_DATABASE_URL is set (an EMPTY, migrated database; the tests write to it):

    WOI_TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/woi_test uv run pytest tests/integration -q
"""
import os
import uuid
from datetime import UTC, datetime, timedelta

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
              "source": "Owner dataset (test)", "license": "Owner permission", "provenance": "Supplied by the test suite; not real religious content.",
              "source_work": "Test fixture work", "language": "en", "attributes": {"reliability": "established"}}
    upload = {"records": [record, {**record, "title": ""}, {"nonsense": True}]}
    # preview writes nothing and reports every problem; a strict import of the same file is refused as a whole
    preview = (await admin.post("/api/v1/admin/datasets/seerah/preview", headers=headers, json=upload)).json()
    assert (preview["valid"], preview["would_create"], preview["failed"]) == (1, 1, 2)
    strict = (await admin.post("/api/v1/admin/datasets/seerah/import", headers=headers, json=upload)).json()
    assert strict["status"] == "failed" and strict["created"] == 0 and strict["failed"] == 2
    assert (await admin.get("/api/v1/admin/datasets/seerah/imports")).json()["imports"][0]["status"] == "failed"
    upload["allow_partial"] = True
    r = await admin.post("/api/v1/admin/datasets/seerah/import", headers=headers, json=upload)
    body = r.json()
    assert r.status_code == 200 and (body["created"], body["failed"]) == (1, 2) and len(body["failures"]) == 2
    first_import = body["id"]
    assert (await admin.post("/api/v1/admin/datasets/seerah/import", headers=headers, json=upload)).json()["id"] == first_import  # idempotent
    provenance = (await admin.get("/api/v1/admin/datasets/seerah/provenance")).json()
    assert provenance["dataset"]["id"] == "seerah" and provenance["imports"] and any(e["action"] == "dataset.import" for e in provenance["events"])

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
    assert body["status"] == "insufficient" and body["message"] == "Insufficient verified sources." and body["authority_summary"] == {"unavailable": 1}
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
    assert all(i["authority_class"] == "primary_source" and i["verification_state"] for i in body["sections"]["primary_source"]) and body["authority_summary"] == {"primary_source": 2}
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


async def _drop_datasets(*keys):
    """Leave the database as the other tests expect to find it (their datasets are re-created from the manifest on demand)."""
    from sqlalchemy import text
    from app.core.config import get_settings
    from app.db.session import Database
    db = Database(get_settings())
    async with db.session_factory() as session:
        for key in keys:
            await session.execute(text("delete from data_sets where dataset_key = :k"), {"k": key})
        await session.commit()
    await db.dispose()


async def test_unpublish_withdraws_a_published_dataset_and_assistant_lists_sourced_records(app_client, monkeypatch):
    """A published, sourced record is retrieved with its metadata; unpublishing removes it everywhere at once."""
    from sqlalchemy import text
    from app.core.config import get_settings
    from app.db.session import Database
    db = Database(get_settings())
    async with db.session_factory() as session:
        await session.execute(text("delete from data_sets where dataset_key = 'aqeedah'"))
        await session.commit()
    await db.dispose()
    admin, headers, _ = await make_user(app_client, admin=True)
    assert (await admin.post("/api/v1/admin/datasets/manifest/sync", headers=headers)).status_code == 200
    record = {"id": "aq-1", "entity_type": "aqeedah", "title": "Patience in hardship (fixture)", "description": "Fixture record about patience in hardship, written for the test suite only.",
              "source": "Test fixture", "license": "Owner permission", "provenance": "Written by the test suite; not real religious content.", "source_work": "Fixture work",
              "edition": "Fixture edition", "page": "12", "chapter": "Fixture chapter", "language": "en", "provenance_status": "source_and_page_cited",
              "attributes": {"school": "Fixture school", "topic": "patience", "statement": "A fixture statement.", "quran_refs": ["2:153"]}}
    other = {**record, "id": "aq-2", "attributes": {**record["attributes"], "school": "Another fixture school", "statement": "A different fixture statement."}}
    assert (await admin.post("/api/v1/admin/datasets/aqeedah/import", headers=headers, json={"records": [record, other]})).json()["created"] == 2
    await admin.post("/api/v1/admin/datasets/aqeedah/action", headers=headers, json={"action": "mark_verified", "note": "Checked the fixture records by hand."})
    confirm = {"action": "publish", "confirmed_by": "Owner", "confirmed_on": "2026-10-01", "basis": "written permission (test)"}
    assert (await admin.post("/api/v1/admin/datasets/aqeedah/action", headers=headers, json=confirm)).status_code == 200

    both = (await app_client.get("/api/v1/knowledge/records?type=aqeedah&topic=patience")).json()
    assert both["total"] == 2  # two schools, two separate records
    one = (await app_client.get("/api/v1/knowledge/records?type=aqeedah&school=Another%20fixture%20school")).json()
    assert one["total"] == 1 and one["items"][0]["attributes"]["statement"] == "A different fixture statement." and one["items"][0]["page"] == "12"

    from app.api.routes import assistant as route

    async def no_evidence(db, corpora, question, limit):
        return []
    monkeypatch.setattr(route, "search_evidence", no_evidence)
    client, user_headers, _ = await make_user(app_client)
    r = await client.post("/api/v1/assistant/query", headers=user_headers, json={"question": "What does the Qur'an say about patience in hardship?"})
    body = r.json()
    assert body["status"] == "insufficient"  # no primary source: the assistant still abstains
    labels = {k["label"]: k for k in body["knowledge_sources"]}
    assert len(labels) == 2 and all(k["source_work"] == "Fixture work" and "p. 12" in k["locator"] for k in labels.values())
    assert {k["position"] for k in labels.values()} == {"Fixture school", "Another fixture school"}
    assert all(any("not the only one" in n for n in k["uncertainty"]) for k in labels.values())
    # an unreviewed record is labelled unverified, never as a source of authority; every item says where it is from and how verified it is
    assert all(k["authority_class"] == "unverified" and k["source_title"] == "Fixture work" and k["edition"] == "Fixture edition" and k["record"]["dataset"] == "aqeedah" and "unreviewed" in k["verification_state"] for k in labels.values())
    assert body["authority_summary"] == {"unverified": 2}

    assert (await admin.post("/api/v1/admin/datasets/aqeedah/action", headers=headers, json={"action": "unpublish"})).json()["publication_status"] == "staged"
    assert (await app_client.get("/api/v1/knowledge/records?type=aqeedah")).json()["total"] == 0
    body = (await client.post("/api/v1/assistant/query", headers=user_headers, json={"question": "What does the Qur'an say about patience in hardship?"})).json()
    assert body["knowledge_sources"] == []
    await _drop_datasets("aqeedah")


async def test_expired_jobs_and_finished_events_disappear_and_job_fields_are_enforced(app_client):
    from sqlalchemy import text
    from app.core.config import get_settings
    from app.db.session import Database
    db = Database(get_settings())
    async with db.session_factory() as session:
        await session.execute(text("delete from data_sets where dataset_key = 'directory-jobs'"))
        await session.commit()
    await db.dispose()
    admin, headers, _ = await make_user(app_client, admin=True)
    assert (await admin.post("/api/v1/admin/datasets/manifest/sync", headers=headers)).status_code == 200
    unique = uuid.uuid4().hex[:8]
    job = {"listing_type": "job", "name": f"Analyst {unique}", "source": "Employer feed (test)", "license": "Employer terms (test)", "provenance": "Posted by the test suite",
           "external_key": f"job-{unique}", "country": "GB", "city": "Leeds", "attributes": {"employer": "Example Ltd", "application_url": "https://example.org/apply", "employment_type": "full_time"}}
    soon = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    past = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    rows = [{**job, "expires_at": soon}, {**job, "external_key": f"old-{unique}", "name": f"Closed {unique}", "expires_at": past},
            {**job, "external_key": f"bad-{unique}", "name": f"Missing {unique}", "attributes": {"employer": "X"}, "expires_at": soon}]
    r = await admin.post("/api/v1/admin/datasets/directory-jobs/import-listings", headers=headers, json={"records": rows})
    assert r.json()["status"] == "failed" and r.json()["failures"][0]["index"] == 2  # all-or-nothing: the invalid row blocks the file
    r = await admin.post("/api/v1/admin/datasets/directory-jobs/import-listings", headers=headers, json={"records": rows[:2]})
    assert r.json()["created"] == 2
    await admin.post("/api/v1/admin/datasets/directory-jobs/action", headers=headers, json={"action": "mark_verified", "note": "Checked the two test jobs by hand."})
    assert (await admin.post("/api/v1/admin/datasets/directory-jobs/action", headers=headers, json={"action": "publish", "confirmed_by": "Owner", "confirmed_on": "2026-10-01", "basis": "test"})).status_code == 200
    found = (await app_client.get(f"/api/v1/directory/listings?type=job&q={unique}")).json()
    assert [i["name"] for i in found["items"]] == [f"Analyst {unique}"]  # the closed job is not listed
    assert found["items"][0]["attributes"]["application_url"] == "https://example.org/apply" and found["items"][0]["expires_at"]
    await _drop_datasets("directory-jobs")


async def test_domain_dashboard_is_honest_and_downgrades_without_live_data(app_client):
    admin, headers, _ = await make_user(app_client, admin=True)
    assert (await admin.post("/api/v1/admin/datasets/manifest/sync", headers=headers)).status_code == 200
    body = (await app_client.get("/api/v1/knowledge/domains")).json()
    by = {d["domain"]: d for d in body["domains"]}
    assert len(by) == 22 and set(body["statuses"]) >= {"READY", "EMPTY", "SOURCE_BLOCKED", "RIGHTS_UNVERIFIED"}
    # this scratch database holds no Qur'an: the declared READY must not be shown
    assert by["quran"]["declared_status"] == "READY" and by["quran"]["status"] != "READY" and by["quran"]["why_not_ready"]
    assert by["hadith_gradings"]["status"] == "RIGHTS_UNVERIFIED" and by["fiqh"]["status"] == "EMPTY"
    assert all(d["why_not_ready"] for d in body["domains"] if d["status"] != "READY")
    full = (await admin.get("/api/v1/admin/datasets/readiness")).json()
    assert {g for g in full["domains"][0]["gates"]} and (await app_client.get("/api/v1/admin/datasets/readiness")).status_code == 401


async def test_importer_lifecycle_preview_run_idempotent_failsafe_and_rollback(app_client, monkeypatch):
    """A registered adapter runs all-or-nothing, records its source version and checksum, and is safe to re-run."""
    from app.importers import ADAPTERS
    from app.importers.base import AdapterResult, FetchResult, SourceAdapter
    unique = uuid.uuid4().hex[:8]

    class Stub(SourceAdapter):
        id, dataset_key, kind, title = "stub-mosques", "directory-mosques", "listings", "Stub (test fixture, not real data)"
        probe_urls, licence_summary = ("https://example.invalid/",), "test fixture"
        bad = False

        def fetch(self, params):
            return FetchResult(version="stub-1", checksum="a" * 64, payload=None, source_url="https://example.org/stub")

        def build(self, fetched, params):
            rows = [{"external_key": f"stub:{unique}:{i}", "listing_type": "mosque", "name": f"Fixture Masjid {unique} {i}", "country": "ZZ", "latitude": 1.0 + i / 1000, "longitude": 2.0,
                     "source": "Stub", "license": "test fixture", "provenance": "Generated by the test suite; not a real place.", "source_updated_at": "2026-10-01"} for i in range(3)]
            if self.bad:
                rows.append({"listing_type": "mosque", "name": "x", "latitude": 999, "longitude": 0, "source": "s", "license": "l", "provenance": "p"})
            return AdapterResult(rows=rows, skipped={}, stats={"rows": len(rows)})

    stub = Stub()
    monkeypatch.setitem(ADAPTERS, stub.id, stub)
    admin, headers, _ = await make_user(app_client, admin=True)
    assert (await admin.post("/api/v1/admin/datasets/manifest/sync", headers=headers)).status_code == 200
    listing = (await admin.get("/api/v1/admin/datasets/importers/list")).json()["importers"]
    assert {"geoalgeria-mosquees", "hadith-api-grades", "osm-overpass-mosques", "stub-mosques"} <= {i["id"] for i in listing}
    assert (await app_client.post("/api/v1/admin/datasets/importers/stub-mosques/preview", json={"params": {}})).status_code in {401, 403}

    preview = (await admin.post("/api/v1/admin/datasets/importers/stub-mosques/preview", headers=headers, json={"params": {}})).json()
    assert preview["applied"] is False and preview["preview"]["would_create"] == 3 and preview["source_version"] == "stub-1"
    before = (await admin.get("/api/v1/admin/datasets")).json()["datasets"]
    assert next(d for d in before if d["id"] == "directory-mosques")["record_count"] == 0       # preview wrote nothing

    stub.bad = True
    failed = (await admin.post("/api/v1/admin/datasets/importers/stub-mosques/run", headers=headers, json={"params": {}})).json()
    assert failed["status"] == "failed" and failed["created"] == 0 and failed["failed"] == 1     # one invalid row: nothing imported
    stub.bad = False
    run = (await admin.post("/api/v1/admin/datasets/importers/stub-mosques/run", headers=headers, json={"params": {}})).json()
    assert run["status"] == "applied" and run["created"] == 3
    again = (await admin.post("/api/v1/admin/datasets/importers/stub-mosques/run", headers=headers, json={"params": {}})).json()
    assert again["import_id"] == run["import_id"]                                                 # re-running an unchanged source changes nothing

    history = (await admin.get("/api/v1/admin/datasets/directory-mosques/provenance")).json()["imports"]
    applied = next(i for i in history if i["id"] == run["import_id"])
    assert applied["adapter_id"] == "stub-mosques" and applied["source_version"] == "stub-1" and applied["source_checksum"] == "a" * 64
    conflicts = (await admin.get("/api/v1/admin/datasets/directory-mosques/conflicts")).json()
    assert conflicts["kind"] == "listings" and "totals" in conflicts
    quality = (await admin.get("/api/v1/admin/datasets/quality-report")).json()
    assert quality["directory_listings"]["total"] >= 3 and quality["directory_listings"]["unverified"] >= 3

    assert (await admin.post(f"/api/v1/admin/datasets/imports/{run['import_id']}/rollback", headers=headers)).json()["status"] == "rolled_back"
    assert next(d for d in (await admin.get("/api/v1/admin/datasets")).json()["datasets"] if d["id"] == "directory-mosques")["record_count"] == 0
    await _drop_datasets("directory-mosques")


async def test_directory_coverage_states_only_the_countries_that_have_data(app_client):
    body = (await app_client.get("/api/v1/directory/coverage")).json()
    assert "items" in body and "countries_by_type" in body and "absence" in body["statement"]


async def test_publication_policy_can_be_scoped_to_one_dataset(app_client):
    """An administrator's action touches only that dataset's content rows (a full pass takes minutes on a populated database)."""
    from app.core.config import get_settings
    from app.db.session import Database
    from app.services.manifest import load_manifest
    from app.services.publication_policy import apply_manifest_policy
    db = Database(get_settings())
    async with db.session_factory() as session:
        manifest = load_manifest()
        assert await apply_manifest_policy(session, manifest, only=["directory-mosques"]) == []          # no content-table targets: nothing to do
        scoped = await apply_manifest_policy(session, manifest, only=["quran-translation-pickthall"])
        assert [r["dataset"] for r in scoped] == ["quran-translation-pickthall"]
        everything = await apply_manifest_policy(session, manifest)
        assert len(everything) > 5 and "quran-translation-pickthall" in {r["dataset"] for r in everything}
        await session.rollback()
    await db.dispose()
