"""Tests for the campaign/job engine: state machine legality, credit
reservation/release, permission and entitlement enforcement on the HTTP
routes, and the idempotency/concurrency primitives the worker's task chain
relies on (`lock_task_for_processing`, `acquire_tenant_slot`/
`release_tenant_slot`). The actual page-fan-out Celery task chain
(`worker.campaign_tasks`) lives in the `gridkeep-worker` package and is
covered by that package's own test suite, since `gridkeep-api` cannot
depend on it (see docs/adr/0008).
"""

import uuid
from datetime import UTC, datetime

import pytest
from app.core.db import set_tenant_context
from app.core.exceptions import ConflictError
from app.modules.campaign_jobs import repositories as jobs_repo
from app.modules.campaign_jobs.concurrency import acquire_tenant_slot, release_tenant_slot
from app.modules.campaigns import repositories as campaigns_repo
from app.modules.campaigns import state_machine
from app.modules.tenancy import repositories as tenancy_repo
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.helpers import (
    csrf_headers,
    extract_token_from_url,
    migrator_asyncpg_url,
    register_verify_login,
)

pytestmark = pytest.mark.asyncio

STRONG_PASSWORD = "CorrectHorse9Battery"

CAMPAIGN_PAYLOAD = {
    "name": "Dubai Marina Restaurants",
    "source_key": "mock",
    "result_limit": 40,
    "industry": "Restaurants",
    "category": "Restaurants",
    "country": "United Arab Emirates",
    "city": "Dubai",
    "area": "Dubai Marina",
    "min_rating": 3.5,
    "min_reviews": 20,
    "must_have_phone": True,
    "website_requirement": "any",
}


async def _register_owner_and_create_tenant(client, smtp_capture, *, email: str, tenant_name: str):
    await register_verify_login(
        client, smtp_capture, email=email, password=STRONG_PASSWORD, full_name="Owner"
    )
    resp = await client.post("/tenants", json={"name": tenant_name}, headers=csrf_headers(client))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _create_estimate_launch(
    client, *, name: str = "Dubai Marina Restaurants", result_limit: int = 40
):
    payload = dict(CAMPAIGN_PAYLOAD, name=name, result_limit=result_limit)
    resp = await client.post("/campaigns", json=payload, headers=csrf_headers(client))
    assert resp.status_code == 200, resp.text
    campaign_id = resp.json()["id"]

    resp = await client.post(f"/campaigns/{campaign_id}/estimate", headers=csrf_headers(client))
    assert resp.status_code == 200, resp.text

    resp = await client.post(f"/campaigns/{campaign_id}/launch", headers=csrf_headers(client))
    assert resp.status_code == 200, resp.text
    return campaign_id, resp.json()


def _session_factory():
    engine = create_async_engine(migrator_asyncpg_url())
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


async def test_state_machine_rejects_illegal_transition():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await tenancy_repo.create_tenant(
                session, name="Illegal Transition Tenant", slug=f"itt-{uuid.uuid4().hex[:10]}"
            )
            campaign = await campaigns_repo.create_campaign(
                session,
                tenant_id=tenant.id,
                name="Illegal Transition Test",
                source_key="mock",
                result_limit=10,
                created_by_user_id=None,
            )
            await session.commit()

            assert campaign.status == "draft"
            with pytest.raises(ConflictError):
                # draft -> running is not a legal transition (must go
                # through estimating/ready/queued first).
                await state_machine.transition(session, campaign, to_status="running")
    finally:
        await engine.dispose()


async def test_state_machine_is_terminal():
    for status in ("completed", "cancelled", "failed", "partially_completed"):
        assert state_machine.is_terminal(status)
    for status in ("draft", "estimating", "ready", "queued", "running", "pausing", "paused"):
        assert not state_machine.is_terminal(status)


# ---------------------------------------------------------------------------
# HTTP lifecycle, permissions, entitlements
# ---------------------------------------------------------------------------


async def test_launch_reserves_credits_against_the_wallet(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="campaign-owner1@example.com", tenant_name="Campaign Co 1"
    )
    wallet_before = (await client.get("/usage/wallet")).json()
    assert wallet_before["balance"] == 250.0

    _campaign_id, campaign = await _create_estimate_launch(client)
    assert campaign["status"] == "queued"

    wallet_after = (await client.get("/usage/wallet")).json()
    # 40 results at 1 credit/result = 40 credits reserved (not yet debited -
    # reservations reduce *available*, the ledger balance itself only
    # changes once the worker commits the reservation).
    assert wallet_after["balance"] == 250.0
    assert wallet_after["available"] == 210.0


async def test_launch_blocked_by_max_concurrent_campaigns_entitlement(client, smtp_capture):
    """Trial plan caps max_concurrent_campaigns at 1 (see seed_data.py).
    A second campaign cannot be launched while the first is still active -
    enforced server-side via the entitlement resolver, never a frontend
    check."""
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="campaign-owner2@example.com", tenant_name="Campaign Co 2"
    )
    await _create_estimate_launch(client, name="First Campaign", result_limit=10)

    payload = dict(CAMPAIGN_PAYLOAD, name="Second Campaign", result_limit=10)
    resp = await client.post("/campaigns", json=payload, headers=csrf_headers(client))
    campaign_id = resp.json()["id"]
    await client.post(f"/campaigns/{campaign_id}/estimate", headers=csrf_headers(client))

    launch_resp = await client.post(
        f"/campaigns/{campaign_id}/launch", headers=csrf_headers(client)
    )
    assert launch_resp.status_code == 402, launch_resp.text
    assert launch_resp.json()["error"]["code"] == "entitlement_denied"


async def test_pause_and_cancel_require_the_right_source_status(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="campaign-owner3@example.com", tenant_name="Campaign Co 3"
    )
    campaign_id, campaign = await _create_estimate_launch(client)
    assert campaign["status"] == "queued"

    # A freshly-queued campaign (no worker has picked it up yet in this
    # HTTP-only test) is not "running" yet, so pause must be rejected.
    pause_resp = await client.post(f"/campaigns/{campaign_id}/pause", headers=csrf_headers(client))
    assert pause_resp.status_code == 409, pause_resp.text
    assert pause_resp.json()["error"]["code"] == "conflict"

    # "queued" -> "cancelling" is legal though (see LEGAL_TRANSITIONS).
    cancel_resp = await client.post(
        f"/campaigns/{campaign_id}/cancel", headers=csrf_headers(client)
    )
    assert cancel_resp.status_code == 200, cancel_resp.text
    assert cancel_resp.json()["status"] == "cancelling"

    # Cancelling twice is not legal (cancelling has no self-transition).
    cancel_again = await client.post(
        f"/campaigns/{campaign_id}/cancel", headers=csrf_headers(client)
    )
    assert cancel_again.status_code == 409


async def test_cancel_from_paused_releases_reservation_synchronously(client, smtp_capture):
    """Exercises `_finalize_cancelled_synchronously`: a paused campaign has
    no in-flight task for a worker to observe "cancelling" on, so
    `cancel_campaign` must finalize (and release the credit reservation)
    immediately, in the request itself."""
    tenant = await _register_owner_and_create_tenant(
        client, smtp_capture, email="campaign-owner4@example.com", tenant_name="Campaign Co 4"
    )
    campaign_id, _campaign = await _create_estimate_launch(client, result_limit=25)

    wallet_while_queued = (await client.get("/usage/wallet")).json()
    assert wallet_while_queued["available"] == 225.0

    # Drive the campaign to "paused" the same way the worker would
    # (queued -> running -> pausing -> paused), directly through the real
    # service/state-machine functions rather than raw SQL, to reach a state
    # HTTP alone cannot produce without a live worker attached.
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant_id = uuid.UUID(tenant["id"])
            await set_tenant_context(session, tenant_id)
            campaign = await state_machine.get_campaign_or_raise(session, uuid.UUID(campaign_id))
            await state_machine.transition(session, campaign, to_status="running")
            await state_machine.transition(session, campaign, to_status="pausing")
            await state_machine.transition(session, campaign, to_status="paused")
            await session.commit()
    finally:
        await engine.dispose()

    cancel_resp = await client.post(
        f"/campaigns/{campaign_id}/cancel", headers=csrf_headers(client)
    )
    assert cancel_resp.status_code == 200, cancel_resp.text
    assert cancel_resp.json()["status"] == "cancelled"

    wallet_after_cancel = (await client.get("/usage/wallet")).json()
    # No task ever ran (0 businesses found), so the whole 25-credit
    # reservation must be released, not partially committed.
    assert wallet_after_cancel["balance"] == 250.0
    assert wallet_after_cancel["available"] == 250.0

    txns = (await client.get("/usage/transactions")).json()
    assert not any(t["type"] == "debit_usage" for t in txns)


async def test_read_only_viewer_can_view_but_not_mutate_campaigns(
    client, client_factory, smtp_capture
):
    tenant = await _register_owner_and_create_tenant(
        client, smtp_capture, email="campaign-owner5@example.com", tenant_name="Campaign Co 5"
    )
    campaign_id, _campaign = await _create_estimate_launch(client, result_limit=10)

    roles = {r["name"]: r["id"] for r in (await client.get("/tenants/roles")).json()}
    invite_resp = await client.post(
        "/tenants/invitations",
        json={"email": "viewer5@example.com", "role_id": roles["Read-Only Viewer"]},
        headers=csrf_headers(client),
    )
    assert invite_resp.status_code == 200, invite_resp.text

    invite_token = extract_token_from_url(
        smtp_capture.latest_body_for("viewer5@example.com"), "token"
    )

    viewer = client_factory()
    await register_verify_login(
        viewer,
        smtp_capture,
        email="viewer5@example.com",
        password=STRONG_PASSWORD,
        full_name="Viewer",
    )
    accept = await viewer.post(
        "/invitations/accept", json={"token": invite_token}, headers=csrf_headers(viewer)
    )
    assert accept.status_code == 200, accept.text
    switch = await viewer.post(
        "/tenants/switch", json={"tenant_id": tenant["id"]}, headers=csrf_headers(viewer)
    )
    assert switch.status_code == 200

    view_resp = await viewer.get(f"/campaigns/{campaign_id}")
    assert view_resp.status_code == 200

    denied_create = await viewer.post(
        "/campaigns", json=CAMPAIGN_PAYLOAD, headers=csrf_headers(viewer)
    )
    assert denied_create.status_code == 403
    assert denied_create.json()["error"]["code"] == "permission_denied"

    denied_cancel = await viewer.post(
        f"/campaigns/{campaign_id}/cancel", headers=csrf_headers(viewer)
    )
    assert denied_cancel.status_code == 403
    assert denied_cancel.json()["error"]["code"] == "permission_denied"


async def test_score_businesses_route_requires_leads_score_permission(
    client, client_factory, smtp_capture
):
    tenant = await _register_owner_and_create_tenant(
        client, smtp_capture, email="campaign-owner7@example.com", tenant_name="Campaign Co 7"
    )
    campaign_id, _campaign = await _create_estimate_launch(client, result_limit=10)

    # No worker runs in this API-only test process, so the campaign never
    # discovers any businesses - this checks routing/permission wiring,
    # not scoring correctness (that's `scoring.score_businesses_for_campaign`'s
    # own direct-session coverage in test_lead_scoring.py).
    owner_resp = await client.post(
        f"/campaigns/{campaign_id}/score-businesses", headers=csrf_headers(client)
    )
    assert owner_resp.status_code == 200, owner_resp.text
    assert owner_resp.json() == []

    roles = {r["name"]: r["id"] for r in (await client.get("/tenants/roles")).json()}
    invite_resp = await client.post(
        "/tenants/invitations",
        json={"email": "viewer7@example.com", "role_id": roles["Read-Only Viewer"]},
        headers=csrf_headers(client),
    )
    assert invite_resp.status_code == 200, invite_resp.text
    invite_token = extract_token_from_url(
        smtp_capture.latest_body_for("viewer7@example.com"), "token"
    )

    viewer = client_factory()
    await register_verify_login(
        viewer,
        smtp_capture,
        email="viewer7@example.com",
        password=STRONG_PASSWORD,
        full_name="Viewer",
    )
    accept = await viewer.post(
        "/invitations/accept", json={"token": invite_token}, headers=csrf_headers(viewer)
    )
    assert accept.status_code == 200, accept.text
    switch = await viewer.post(
        "/tenants/switch", json={"tenant_id": tenant["id"]}, headers=csrf_headers(viewer)
    )
    assert switch.status_code == 200

    denied = await viewer.post(
        f"/campaigns/{campaign_id}/score-businesses", headers=csrf_headers(viewer)
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "permission_denied"


async def test_create_campaign_rejects_unknown_source_key(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="campaign-owner6@example.com", tenant_name="Campaign Co 6"
    )
    payload = dict(CAMPAIGN_PAYLOAD, source_key="nonexistent-connector")
    resp = await client.post("/campaigns", json=payload, headers=csrf_headers(client))
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "validation_error"


async def test_create_campaign_rejects_rating_filters_for_osm_source(client, smtp_capture):
    # OverpassConnector.supports_rating_filter = False - OSM has no
    # rating/review schema at all, so a campaign requesting min_rating/
    # min_reviews against this source is rejected outright rather than
    # silently created and never enforced (see docs/adr/0028).
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="campaign-owner8@example.com", tenant_name="Campaign Co 8"
    )
    payload = dict(CAMPAIGN_PAYLOAD, source_key="osm")  # min_rating/min_reviews already set
    resp = await client.post("/campaigns", json=payload, headers=csrf_headers(client))
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "validation_error"


async def test_create_campaign_accepts_osm_source_without_rating_filters(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="campaign-owner9@example.com", tenant_name="Campaign Co 9"
    )
    payload = dict(CAMPAIGN_PAYLOAD, source_key="osm", min_rating=None, min_reviews=None)
    resp = await client.post("/campaigns", json=payload, headers=csrf_headers(client))
    assert resp.status_code == 200, resp.text
    assert resp.json()["source_key"] == "osm"


# ---------------------------------------------------------------------------
# Idempotency and concurrency primitives (used directly by the worker)
# ---------------------------------------------------------------------------


async def test_lock_task_for_processing_is_idempotent(client, smtp_capture):
    tenant = await _register_owner_and_create_tenant(
        client, smtp_capture, email="campaign-owner7@example.com", tenant_name="Campaign Co 7"
    )
    campaign_id, _campaign = await _create_estimate_launch(client, result_limit=10)

    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant_id = uuid.UUID(tenant["id"])
            await set_tenant_context(session, tenant_id)
            job = await jobs_repo.get_latest_job_for_campaign(session, uuid.UUID(campaign_id))
            tasks = await jobs_repo.list_tasks_for_job(session, job.id)
            task_id = tasks[0].id

            first_lock = await jobs_repo.lock_task_for_processing(
                session, task_id, locked_by="worker-a", now=datetime.now(UTC)
            )
            assert first_lock is not None
            assert first_lock.status == "running"
            await session.commit()

            # A duplicate Celery delivery of the same task must be a no-op:
            # the task is no longer "pending", so a second lock attempt
            # (even from a different worker id) returns None instead of
            # double-processing the page.
            second_lock = await jobs_repo.lock_task_for_processing(
                session, task_id, locked_by="worker-b", now=datetime.now(UTC)
            )

            assert second_lock is None
    finally:
        await engine.dispose()


async def test_per_tenant_concurrency_slots_are_exhausted_and_released():
    tenant_id = str(uuid.uuid4())

    slot0 = await acquire_tenant_slot(tenant_id, "task-1")
    slot1 = await acquire_tenant_slot(tenant_id, "task-2")
    assert {slot0, slot1} == {0, 1}

    # Both of this tenant's slots (MAX_CONCURRENT_TASKS_PER_TENANT=2) are
    # held - a third task must not be able to acquire one.
    slot2 = await acquire_tenant_slot(tenant_id, "task-3")
    assert slot2 is None

    # Releasing with the wrong task_id must not free someone else's slot.
    await release_tenant_slot(tenant_id, slot0, "not-the-holder")
    still_blocked = await acquire_tenant_slot(tenant_id, "task-4")
    assert still_blocked is None

    await release_tenant_slot(tenant_id, slot0, "task-1")
    reacquired = await acquire_tenant_slot(tenant_id, "task-5")
    assert reacquired == slot0
