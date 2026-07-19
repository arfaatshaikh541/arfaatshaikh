"""Tests for `worker.integration_tasks.push_lead_to_integration` - the
outbound webhook delivery task: signs the payload, posts it through the
SSRF-safe `safe_post_json`, and records the result. `safe_post_json`
itself (the SSRF-blocking behavior) is tested directly in
`test_crawler_safety.py`; these tests focus on what's specific to this
task - signing, status transitions, and the permanent-vs-transient
failure distinction - by monkeypatching `it.safe_post_json` the same way
`test_enrichment_tasks.py` monkeypatches `et.crawl_site`.
"""

import json
import uuid
from datetime import UTC, datetime

import pytest
from app.core.security import encrypt_credential, sign_payload
from app.modules.businesses import repositories as businesses_repo
from app.modules.integrations import repositories as integrations_repo
from app.modules.integrations.models import Integration, IntegrationDelivery
from app.modules.leads import scoring
from app.modules.tenancy import repositories as tenancy_repo
from sqlalchemy.ext.asyncio import async_sessionmaker
from worker import integration_tasks as it
from worker.crawler.safety import FetchError, SafeResponse, UnsafeUrlError

pytestmark = pytest.mark.asyncio


async def _make_tenant(session):
    return await tenancy_repo.create_tenant(
        session, name="Integration Test Co", slug=f"int-{uuid.uuid4().hex[:10]}"
    )


async def _make_lead(session, *, tenant_id, native_id="Joe's Pizza"):
    business = await businesses_repo.upsert_business_from_discovery(
        session,
        tenant_id=tenant_id,
        campaign_id=None,
        record={
            "source": "mock",
            "source_native_id": native_id,
            "source_url": "https://mock-source.example.com/place/1",
            "collected_at": datetime.now(UTC).isoformat(),
            "name": native_id,
            "category": "Restaurant",
        },
    )
    lead, _score, _o, _r = await scoring.score_lead(session, business.id)
    return lead


async def _make_integration(session, *, tenant_id, webhook_url="https://example.com/hook"):
    integration = Integration(
        tenant_id=tenant_id,
        name="Test Webhook",
        type="webhook",
        webhook_url=webhook_url,
        webhook_secret_encrypted=encrypt_credential("shh-webhook-secret"),
    )
    session.add(integration)
    await session.flush()
    return integration


async def test_successful_push_signs_payload_and_records_success(migrator_session, monkeypatch):
    session = migrator_session
    tenant = await _make_tenant(session)
    lead = await _make_lead(session, tenant_id=tenant.id)
    integration = await _make_integration(session, tenant_id=tenant.id)
    delivery = await integrations_repo.create_delivery(
        session,
        tenant_id=tenant.id,
        integration_id=integration.id,
        lead_id=lead.id,
        payload={"event": "lead.pushed", "lead": {"id": str(lead.id)}},
        triggered_by_user_id=None,
    )
    await session.commit()

    captured: dict = {}

    async def fake_safe_post_json(url, *, json_body, headers=None):
        captured["url"] = url
        captured["json_body"] = json_body
        captured["headers"] = headers
        return SafeResponse(url=url, status_code=200, headers={}, text="thanks", used_https=True)

    monkeypatch.setattr(it, "safe_post_json", fake_safe_post_json)
    await it._run_push_async(str(delivery.id))

    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)
    async with session_factory() as verify_session:
        refreshed = await integrations_repo.get_delivery(verify_session, delivery.id)
        assert refreshed.status == "success"
        assert refreshed.http_status_code == 200
        assert refreshed.delivered_at is not None
        assert refreshed.attempt_count == 1
        # Signed bytes must match exactly what the DB's own JSONB round
        # trip produces (Postgres does not preserve original key
        # insertion order), not the pre-commit in-memory dict - the task
        # signs whatever it actually re-reads from the database.
        expected_signature = sign_payload(
            "shh-webhook-secret",
            json.dumps(refreshed.payload, separators=(",", ":")).encode("utf-8"),
        )

    assert captured["url"] == "https://example.com/hook"
    assert captured["headers"]["X-Gridkeep-Event"] == "lead.pushed"
    assert captured["headers"]["X-Gridkeep-Signature"] == expected_signature


async def test_non_2xx_response_stays_pending_and_raises_for_retry(migrator_session, monkeypatch):
    session = migrator_session
    tenant = await _make_tenant(session)
    lead = await _make_lead(session, tenant_id=tenant.id, native_id="Non 2xx Co")
    integration = await _make_integration(session, tenant_id=tenant.id)
    delivery = await integrations_repo.create_delivery(
        session,
        tenant_id=tenant.id,
        integration_id=integration.id,
        lead_id=lead.id,
        payload={"event": "lead.pushed"},
        triggered_by_user_id=None,
    )
    await session.commit()

    async def failing_safe_post_json(url, *, json_body, headers=None):
        return SafeResponse(url=url, status_code=500, headers={}, text="oops", used_https=True)

    monkeypatch.setattr(it, "safe_post_json", failing_safe_post_json)
    with pytest.raises(FetchError):
        await it._run_push_async(str(delivery.id))

    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)
    async with session_factory() as verify_session:
        refreshed = await integrations_repo.get_delivery(verify_session, delivery.id)
        # Not yet terminal - stays "pending" so a retry can still run
        # (see worker.integration_tasks module docstring).
        assert refreshed.status == "pending"
        assert refreshed.http_status_code == 500
        assert refreshed.attempt_count == 1


async def test_finalize_failed_marks_terminal_status(migrator_session):
    session = migrator_session
    tenant = await _make_tenant(session)
    lead = await _make_lead(session, tenant_id=tenant.id, native_id="Finalize Failed Co")
    integration = await _make_integration(session, tenant_id=tenant.id)
    delivery = await integrations_repo.create_delivery(
        session,
        tenant_id=tenant.id,
        integration_id=integration.id,
        lead_id=lead.id,
        payload={"event": "lead.pushed"},
        triggered_by_user_id=None,
    )
    await session.commit()

    await it._finalize_failed(str(delivery.id), "Webhook responded 500", attempt_count=4)

    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)
    async with session_factory() as verify_session:
        refreshed = await integrations_repo.get_delivery(verify_session, delivery.id)
        assert refreshed.status == "failed"
        assert refreshed.attempt_count == 4
        assert "500" in refreshed.error_message


async def test_unsafe_url_is_never_attempted(migrator_session):
    session = migrator_session
    tenant = await _make_tenant(session)
    lead = await _make_lead(session, tenant_id=tenant.id, native_id="Unsafe URL Co")
    # Constructed directly (bypassing the API's own basic scheme
    # validation) to prove the worker-side SSRF check is the real,
    # load-bearing defense - not the API's input validation.
    integration = await _make_integration(
        session, tenant_id=tenant.id, webhook_url="http://10.0.0.5/hook"
    )
    delivery = await integrations_repo.create_delivery(
        session,
        tenant_id=tenant.id,
        integration_id=integration.id,
        lead_id=lead.id,
        payload={"event": "lead.pushed"},
        triggered_by_user_id=None,
    )
    await session.commit()

    with pytest.raises(UnsafeUrlError):
        await it._run_push_async(str(delivery.id))

    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)
    async with session_factory() as verify_session:
        refreshed = await integrations_repo.get_delivery(verify_session, delivery.id)
        # Never attempted an HTTP call, so still "pending" here - the
        # celery-level wrapper (push_lead_to_integration) is what catches
        # UnsafeUrlError and calls _finalize_failed without retrying.
        assert refreshed.status == "pending"


async def test_celery_wrapper_finalizes_as_failed_once_retries_are_exhausted(monkeypatch):
    """Regression test for the bug documented in docs/adr/0016: Celery's
    `Task.retry(exc=exc, ...)` re-raises the *original* exception (not
    `MaxRetriesExceededError`) once retries are exhausted, so a
    `try: raise self.retry(...) except MaxRetriesExceededError:` pattern
    never actually catches anything on real retry exhaustion - the task
    just dies uncaught, leaving the delivery stuck "pending" forever with
    no error recorded (confirmed against the installed Celery version
    before this fix; see docs/adr/0016). `push_lead_to_integration` now
    checks `self.request.retries >= self.max_retries` *before* calling
    `retry()` at all, avoiding that dead-code path entirely.

    This exercises the real Celery-wrapped task (not `_run_push_async`
    directly), with `push_request` simulating the final attempt.
    `_run_push_async` and `_finalize_failed` are stubbed to trivial,
    non-awaiting coroutines and `run_db_task` to a synchronous driver
    that runs them to completion via a single `send(None)` - deliberately
    not the real `run_db_task` (which calls `asyncio.run(...)`, illegal
    nested inside pytest-asyncio's already-running loop, and which would
    also touch the module-scoped `engine`/redis singletons other tests in
    this session have already bound to that loop). What's under test here
    is purely `push_lead_to_integration`'s own exception-handling control
    flow - that it calls `_finalize_failed` instead of letting the
    original exception re-escape once retries are exhausted - not the
    database work inside those two functions, which `test_finalize_failed_
    marks_terminal_status` above already covers against a real database.
    """
    finalize_calls: list[tuple[str, str, int]] = []

    async def fake_run_push_async(delivery_id_str: str) -> None:
        raise RuntimeError("simulated unanticipated failure (e.g. a missing config value)")

    async def fake_finalize_failed(delivery_id_str: str, message: str, *, attempt_count: int) -> None:
        finalize_calls.append((delivery_id_str, message, attempt_count))

    def fake_run_db_task(coro):
        try:
            coro.send(None)
        except StopIteration as si:
            return si.value
        raise AssertionError("stub coroutine unexpectedly suspended on a real await")

    monkeypatch.setattr(it, "_run_push_async", fake_run_push_async)
    monkeypatch.setattr(it, "_finalize_failed", fake_finalize_failed)
    monkeypatch.setattr(it, "run_db_task", fake_run_db_task)

    task = it.push_lead_to_integration
    assert task.max_retries == 4
    # called_directly=False so `retry()` takes the "real worker" branch
    # instead of the called_directly short-circuit `apply()`/plain-call
    # testing would otherwise hit; retries=max_retries simulates the
    # final attempt, where retrying again is no longer allowed.
    task.push_request(called_directly=False, retries=task.max_retries)
    try:
        task("11111111-1111-1111-1111-111111111111")
    finally:
        task.pop_request()

    assert len(finalize_calls) == 1
    delivery_id, message, attempt_count = finalize_calls[0]
    assert delivery_id == "11111111-1111-1111-1111-111111111111"
    assert "simulated unanticipated failure" in message
    assert attempt_count == task.max_retries + 1


async def test_duplicate_delivery_of_a_non_pending_delivery_is_a_noop(
    migrator_session, monkeypatch
):
    session = migrator_session
    tenant = await _make_tenant(session)
    lead = await _make_lead(session, tenant_id=tenant.id, native_id="Already Done Co")
    integration = await _make_integration(session, tenant_id=tenant.id)
    delivery = IntegrationDelivery(
        tenant_id=tenant.id,
        integration_id=integration.id,
        lead_id=lead.id,
        status="success",
        payload={"event": "lead.pushed"},
        http_status_code=200,
        attempt_count=1,
    )
    session.add(delivery)
    await session.flush()
    await session.commit()

    async def unexpected_call(*args, **kwargs):
        raise AssertionError("must not attempt delivery for an already-handled record")

    monkeypatch.setattr(it, "safe_post_json", unexpected_call)
    await it._run_push_async(str(delivery.id))

    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)
    async with session_factory() as verify_session:
        refreshed = await integrations_repo.get_delivery(verify_session, delivery.id)
        assert refreshed.status == "success"
        assert refreshed.attempt_count == 1
