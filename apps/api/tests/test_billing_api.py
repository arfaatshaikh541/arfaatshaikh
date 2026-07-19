"""HTTP-level tests for the Billing module (Milestone 9): a real Stripe
integration - Checkout Sessions to subscribe/upgrade, Customer Portal
sessions for self-service management, and a webhook handler that is the
sole source of truth for subscription/invoice state.

No live Stripe API key exists in this environment (see ADR-0017), so
Stripe's own outbound SDK calls (`stripe.Customer.create_async`,
`stripe.checkout.Session.create_async`, `stripe.billing_portal.Session.
create_async`) are monkeypatched at the call boundary - the same
"mocked-adapter" discipline ADR-0010's Google Places tests already
established. The webhook *receiver* needs no live key to test for real,
though: Stripe's HMAC-SHA256 webhook signature scheme is fully public
and constructible offline, so every webhook test here POSTs a
genuinely, correctly signed payload through the real signature-
verification code path (`stripe.Webhook.construct_event`), never a
bypassed one.
"""

import hashlib
import hmac
import json
import time

import pytest
import stripe
from app.core.config import get_settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.helpers import csrf_headers, migrator_asyncpg_url, register_verify_login

pytestmark = pytest.mark.asyncio

STRONG_PASSWORD = "CorrectHorse9Battery"
TEST_WEBHOOK_SECRET = "whsec_test_2f8a9c1d4e6b7f3a5c8d9e0f1a2b3c4d"


def _sign_stripe_payload(payload_bytes: bytes, secret: str) -> str:
    """Constructs a real Stripe webhook signature header, following
    Stripe's own public v1 scheme (HMAC-SHA256 over "{timestamp}.{body}")
    - the exact same construction `stripe.Webhook.construct_event` (the
    production code path) verifies against, so this proves the real
    signature-checking logic, not a bypassed one."""
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.".encode() + payload_bytes
    signature = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


async def _register_owner_and_create_tenant(client, smtp_capture, *, email: str, tenant_name: str):
    await register_verify_login(
        client, smtp_capture, email=email, password=STRONG_PASSWORD, full_name="Owner"
    )
    resp = await client.post("/tenants", json={"name": tenant_name}, headers=csrf_headers(client))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _set_plan_stripe_price_id(plan_key: str, stripe_price_id: str) -> None:
    engine = create_async_engine(migrator_asyncpg_url())
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE subscription_plans SET stripe_price_id = :price_id WHERE key = :key"),
            {"price_id": stripe_price_id, "key": plan_key},
        )
    await engine.dispose()


async def _insert_billing_customer(tenant_id: str, stripe_customer_id: str) -> None:
    engine = create_async_engine(migrator_asyncpg_url())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO billing_customers (id, tenant_id, stripe_customer_id, "
                "created_at, updated_at) "
                "VALUES (gen_random_uuid(), :tenant_id, :stripe_customer_id, now(), now())"
            ),
            {"tenant_id": tenant_id, "stripe_customer_id": stripe_customer_id},
        )
    await engine.dispose()


@pytest.fixture(autouse=True)
def _reset_settings_cache_around_test():
    """`get_settings()` is `lru_cache`d; `monkeypatch.setenv` alone does
    NOT invalidate that cache, and monkeypatch's own teardown (reverting
    the env var) happens *after* this test function returns - so without
    clearing the cache again post-teardown, a later test that never calls
    `_enable_stripe` could still observe a previous test's monkeypatched
    Stripe keys via the stale cached `Settings` object. Same discipline
    `conftest.py`'s `moto_s3` fixture already uses for `S3_ENDPOINT_URL`.
    """
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _enable_stripe(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake_not_a_real_key")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    get_settings.cache_clear()


async def test_checkout_session_fails_clearly_when_stripe_not_configured(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="billing-noconfig@example.com", tenant_name="No Stripe Co"
    )
    resp = await client.post(
        "/billing/checkout-session",
        json={"plan_key": "starter"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 409, resp.text
    assert "not configured" in resp.json()["error"]["message"].lower()


async def test_checkout_session_fails_clearly_when_plan_has_no_price_configured(
    client, smtp_capture, monkeypatch
):
    _enable_stripe(monkeypatch)
    # `subscription_plans` is platform catalog data, not truncated between
    # tests by `reset_database` (by design - it's reseeded, not reset, the
    # same way every other milestone's catalog data persists across
    # tests) - "scale" is deliberately the one plan key no other test in
    # this file ever calls `_set_plan_stripe_price_id` on, so this test
    # doesn't depend on execution order to see a NULL price id.
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="billing-noprice@example.com", tenant_name="No Price Co"
    )
    resp = await client.post(
        "/billing/checkout-session",
        json={"plan_key": "scale"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 409, resp.text
    assert "no stripe price configured" in resp.json()["error"]["message"].lower()


async def test_checkout_session_success_creates_billing_customer_and_returns_url(
    client, smtp_capture, monkeypatch
):
    _enable_stripe(monkeypatch)
    await _set_plan_stripe_price_id("starter", "price_fake_starter_123")
    tenant = await _register_owner_and_create_tenant(
        client, smtp_capture, email="billing-checkout@example.com", tenant_name="Checkout Co"
    )

    captured_customer_kwargs = {}
    captured_session_kwargs = {}

    class FakeCustomer:
        id = "cus_fake_123"

    class FakeCheckoutSession:
        url = "https://checkout.stripe.com/fake-session-url"

    async def fake_customer_create(**kwargs):
        captured_customer_kwargs.update(kwargs)
        return FakeCustomer()

    async def fake_checkout_create(**kwargs):
        captured_session_kwargs.update(kwargs)
        return FakeCheckoutSession()

    monkeypatch.setattr(stripe.Customer, "create_async", fake_customer_create)
    monkeypatch.setattr(stripe.checkout.Session, "create_async", fake_checkout_create)

    resp = await client.post(
        "/billing/checkout-session",
        json={"plan_key": "starter"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["checkout_url"] == "https://checkout.stripe.com/fake-session-url"

    assert captured_customer_kwargs["metadata"]["tenant_id"] == tenant["id"]
    assert captured_session_kwargs["customer"] == "cus_fake_123"
    assert captured_session_kwargs["line_items"] == [
        {"price": "price_fake_starter_123", "quantity": 1}
    ]
    assert captured_session_kwargs["metadata"]["tenant_id"] == tenant["id"]

    # A second checkout must reuse the same billing customer, not create
    # a second Stripe Customer for the same tenant.
    captured_customer_kwargs.clear()
    resp2 = await client.post(
        "/billing/checkout-session",
        json={"plan_key": "starter"},
        headers=csrf_headers(client),
    )
    assert resp2.status_code == 200, resp2.text
    assert captured_customer_kwargs == {}


async def test_portal_session_requires_existing_billing_customer(client, smtp_capture, monkeypatch):
    _enable_stripe(monkeypatch)
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="billing-noportal@example.com", tenant_name="No Portal Co"
    )
    resp = await client.post("/billing/portal-session", headers=csrf_headers(client))
    assert resp.status_code == 409, resp.text
    assert "no billing customer" in resp.json()["error"]["message"].lower()


async def test_portal_session_success_for_existing_customer(client, smtp_capture, monkeypatch):
    _enable_stripe(monkeypatch)
    tenant = await _register_owner_and_create_tenant(
        client, smtp_capture, email="billing-portal@example.com", tenant_name="Portal Co"
    )
    await _insert_billing_customer(tenant["id"], "cus_fake_portal_123")

    captured = {}

    class FakePortalSession:
        url = "https://billing.stripe.com/fake-portal-url"

    async def fake_portal_create(**kwargs):
        captured.update(kwargs)
        return FakePortalSession()

    monkeypatch.setattr(stripe.billing_portal.Session, "create_async", fake_portal_create)

    resp = await client.post("/billing/portal-session", headers=csrf_headers(client))
    assert resp.status_code == 200, resp.text
    assert resp.json()["portal_url"] == "https://billing.stripe.com/fake-portal-url"
    assert captured["customer"] == "cus_fake_portal_123"


async def test_billing_manage_permission_enforced(client, smtp_capture, client_factory, monkeypatch):
    """Sales Representative (per the Milestone 1 default catalog) has
    neither `billing.manage` nor `billing.view` - only the dedicated
    "Billing Manager" role and Owner/Administrator do - so it must be
    denied checkout, portal, and invoice-listing alike."""
    _enable_stripe(monkeypatch)
    owner = client
    tenant = await _register_owner_and_create_tenant(
        owner, smtp_capture, email="billing-perm-owner@example.com", tenant_name="Perm Co"
    )

    roles = {r["name"]: r["id"] for r in (await owner.get("/tenants/roles")).json()}
    from tests.helpers import extract_token_from_url

    invite_resp = await owner.post(
        "/tenants/invitations",
        json={"email": "billing-perm-rep@example.com", "role_id": roles["Sales Representative"]},
        headers=csrf_headers(owner),
    )
    assert invite_resp.status_code == 200, invite_resp.text
    invite_token = extract_token_from_url(smtp_capture.latest_body_for("billing-perm-rep@example.com"))

    rep = client_factory()
    await register_verify_login(
        rep, smtp_capture, email="billing-perm-rep@example.com", password=STRONG_PASSWORD, full_name="Rep"
    )
    accept = await rep.post("/invitations/accept", json={"token": invite_token}, headers=csrf_headers(rep))
    assert accept.status_code == 200, accept.text
    switch = await rep.post(
        "/tenants/switch", json={"tenant_id": tenant["id"]}, headers=csrf_headers(rep)
    )
    assert switch.status_code == 200, switch.text

    checkout_resp = await rep.post(
        "/billing/checkout-session", json={"plan_key": "starter"}, headers=csrf_headers(rep)
    )
    assert checkout_resp.status_code == 403, checkout_resp.text

    portal_resp = await rep.post("/billing/portal-session", headers=csrf_headers(rep))
    assert portal_resp.status_code == 403, portal_resp.text

    invoices_resp = await rep.get("/billing/invoices")
    assert invoices_resp.status_code == 403, invoices_resp.text

    # A "Billing Manager" (per the same default catalog) can do all three.
    manager_email = "billing-perm-manager@example.com"
    invite_resp2 = await owner.post(
        "/tenants/invitations",
        json={"email": manager_email, "role_id": roles["Billing Manager"]},
        headers=csrf_headers(owner),
    )
    assert invite_resp2.status_code == 200, invite_resp2.text
    invite_token2 = extract_token_from_url(smtp_capture.latest_body_for(manager_email))

    manager = client_factory()
    await register_verify_login(
        manager, smtp_capture, email=manager_email, password=STRONG_PASSWORD, full_name="Manager"
    )
    accept2 = await manager.post(
        "/invitations/accept", json={"token": invite_token2}, headers=csrf_headers(manager)
    )
    assert accept2.status_code == 200, accept2.text
    switch2 = await manager.post(
        "/tenants/switch", json={"tenant_id": tenant["id"]}, headers=csrf_headers(manager)
    )
    assert switch2.status_code == 200, switch2.text

    manager_invoices_resp = await manager.get("/billing/invoices")
    assert manager_invoices_resp.status_code == 200, manager_invoices_resp.text


async def _tenant_id_from_row(email: str) -> str:
    engine = create_async_engine(migrator_asyncpg_url())
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                "SELECT t.id FROM tenants t "
                "JOIN memberships m ON m.tenant_id = t.id "
                "JOIN users u ON u.id = m.user_id "
                "WHERE u.email = :email"
            ),
            {"email": email},
        )
        tenant_id = result.scalar_one()
    await engine.dispose()
    return str(tenant_id)


async def _wallet_balance(tenant_id: str) -> float:
    engine = create_async_engine(migrator_asyncpg_url())
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT balance FROM credit_wallets WHERE tenant_id = :t"), {"t": tenant_id}
        )
        balance = result.scalar_one()
    await engine.dispose()
    return float(balance)


async def _credit_grant_count_for_reference(reference: str) -> int:
    engine = create_async_engine(migrator_asyncpg_url())
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                "SELECT count(*) FROM credit_transactions "
                "WHERE reference = :reference AND type = 'grant_recurring'"
            ),
            {"reference": reference},
        )
        count = result.scalar_one()
    await engine.dispose()
    return int(count)


def _invoice_paid_event(
    *, event_id: str, invoice_id: str, tenant_id: str, subscription: str | None, price_id: str | None
) -> dict:
    now = int(time.time())
    return {
        "id": event_id,
        "object": "event",
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": invoice_id,
                "object": "invoice",
                "customer": "cus_fake_recurring",
                "subscription": subscription,
                "status": "paid",
                "amount_due": 19900,
                "amount_paid": 19900,
                "currency": "usd",
                "hosted_invoice_url": None,
                "invoice_pdf": None,
                "period_start": now,
                "period_end": now + 30 * 24 * 3600,
                "status_transitions": {"paid_at": now},
                "metadata": {"tenant_id": tenant_id},
                "lines": {
                    "data": (
                        [{"price": {"id": price_id}}] if price_id is not None else []
                    )
                },
            }
        },
    }


async def _post_signed_webhook(client, event: dict):
    payload_bytes = json.dumps(event).encode()
    return await client.post(
        "/billing/webhook",
        content=payload_bytes,
        headers={
            "stripe-signature": _sign_stripe_payload(payload_bytes, TEST_WEBHOOK_SECRET),
            "content-type": "application/json",
        },
    )


async def test_webhook_invoice_paid_grants_recurring_credits_for_configured_plan(
    client, smtp_capture, monkeypatch
):
    """Milestone 13 (ADR-0021): closes the "no recurring credit grant on
    subscription renewal" gap - a paid subscription invoice for a
    configured plan grants that plan's `monthly_credit_grant`, on top of
    the tenant's one-time trial grant already made at signup."""
    _enable_stripe(monkeypatch)
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="billing-recurring-grant@example.com", tenant_name="Recurring Grant Co"
    )
    tenant_id = await _tenant_id_from_row("billing-recurring-grant@example.com")
    await _set_plan_stripe_price_id("starter", "price_starter_fake")
    balance_before = await _wallet_balance(tenant_id)

    event = _invoice_paid_event(
        event_id="evt_recurring_grant_1",
        invoice_id="in_recurring_grant_1",
        tenant_id=tenant_id,
        subscription="sub_recurring_grant_1",
        price_id="price_starter_fake",
    )
    resp = await _post_signed_webhook(client, event)
    assert resp.status_code == 200, resp.text

    balance_after = await _wallet_balance(tenant_id)
    assert balance_after == balance_before + 1000.0  # starter plan's monthly_credit_grant
    assert await _credit_grant_count_for_reference("stripe_invoice:in_recurring_grant_1") == 1


async def test_webhook_invoice_paid_redelivered_under_a_different_event_id_does_not_double_grant(
    client, smtp_capture, monkeypatch
):
    """Stripe's own docs warn a business event can be redelivered under a
    genuinely different event id for the same object - the outer
    `handle_webhook_event` event-id dedup alone would not catch this, so
    the credit grant must be idempotent on the *invoice* id instead (see
    `InvoiceRecord.credit_grant_applied_at`)."""
    _enable_stripe(monkeypatch)
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="billing-recurring-grant-dup@example.com", tenant_name="Dup Grant Co"
    )
    tenant_id = await _tenant_id_from_row("billing-recurring-grant-dup@example.com")
    await _set_plan_stripe_price_id("starter", "price_starter_fake_dup")
    balance_before = await _wallet_balance(tenant_id)

    first_event = _invoice_paid_event(
        event_id="evt_recurring_grant_dup_1",
        invoice_id="in_recurring_grant_dup_1",
        tenant_id=tenant_id,
        subscription="sub_recurring_grant_dup_1",
        price_id="price_starter_fake_dup",
    )
    second_event = _invoice_paid_event(
        event_id="evt_recurring_grant_dup_2",  # different event id
        invoice_id="in_recurring_grant_dup_1",  # same invoice id
        tenant_id=tenant_id,
        subscription="sub_recurring_grant_dup_1",
        price_id="price_starter_fake_dup",
    )

    resp1 = await _post_signed_webhook(client, first_event)
    assert resp1.status_code == 200, resp1.text
    resp2 = await _post_signed_webhook(client, second_event)
    assert resp2.status_code == 200, resp2.text

    balance_after = await _wallet_balance(tenant_id)
    assert balance_after == balance_before + 1000.0  # granted exactly once, not twice
    assert await _credit_grant_count_for_reference("stripe_invoice:in_recurring_grant_dup_1") == 1


async def test_webhook_invoice_paid_with_no_configured_price_grants_nothing(
    client, smtp_capture, monkeypatch
):
    """A paid invoice whose price isn't mapped to any `SubscriptionPlan`
    (an unconfigured/unknown price) must not crash the webhook and must
    not fabricate a grant - it's simply not actionable."""
    _enable_stripe(monkeypatch)
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="billing-recurring-grant-unknown@example.com", tenant_name="Unknown Price Co"
    )
    tenant_id = await _tenant_id_from_row("billing-recurring-grant-unknown@example.com")
    balance_before = await _wallet_balance(tenant_id)

    event = _invoice_paid_event(
        event_id="evt_recurring_grant_unknown_1",
        invoice_id="in_recurring_grant_unknown_1",
        tenant_id=tenant_id,
        subscription="sub_recurring_grant_unknown_1",
        price_id="price_not_configured_anywhere",
    )
    resp = await _post_signed_webhook(client, event)
    assert resp.status_code == 200, resp.text

    balance_after = await _wallet_balance(tenant_id)
    assert balance_after == balance_before
    assert (
        await _credit_grant_count_for_reference("stripe_invoice:in_recurring_grant_unknown_1") == 0
    )


def _build_subscription_event(*, event_id: str, tenant_id: str, price_id: str, status: str = "active") -> dict:
    now = int(time.time())
    return {
        "id": event_id,
        "object": "event",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_fake_1",
                "object": "subscription",
                "customer": "cus_fake_webhook_1",
                "status": status,
                "current_period_start": now,
                "current_period_end": now + 30 * 24 * 3600,
                "cancel_at_period_end": False,
                "metadata": {"tenant_id": tenant_id},
                "items": {
                    "object": "list",
                    "data": [{"id": "si_1", "price": {"id": price_id}}],
                },
            }
        },
    }


async def test_webhook_rejects_invalid_signature(client, monkeypatch):
    _enable_stripe(monkeypatch)
    payload = json.dumps({"id": "evt_bad", "type": "customer.subscription.updated", "data": {"object": {}}}).encode()
    resp = await client.post(
        "/billing/webhook",
        content=payload,
        headers={"stripe-signature": "t=1,v1=deadbeef", "content-type": "application/json"},
    )
    assert resp.status_code == 422, resp.text


async def test_webhook_syncs_tenant_subscription_and_billing_subscription(
    client, smtp_capture, monkeypatch
):
    _enable_stripe(monkeypatch)
    await _set_plan_stripe_price_id("growth", "price_fake_growth_1")
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="billing-webhook-1@example.com", tenant_name="Webhook Co"
    )
    tenant_id = await _tenant_id_from_row("billing-webhook-1@example.com")

    event = _build_subscription_event(
        event_id="evt_sub_update_1", tenant_id=tenant_id, price_id="price_fake_growth_1"
    )
    payload_bytes = json.dumps(event).encode()
    signature = _sign_stripe_payload(payload_bytes, TEST_WEBHOOK_SECRET)

    resp = await client.post(
        "/billing/webhook",
        content=payload_bytes,
        headers={"stripe-signature": signature, "content-type": "application/json"},
    )
    assert resp.status_code == 200, resp.text

    engine = create_async_engine(migrator_asyncpg_url())
    async with engine.begin() as conn:
        sub_row = (
            await conn.execute(
                text("SELECT status, stripe_price_id FROM billing_subscriptions WHERE tenant_id = :t"),
                {"t": tenant_id},
            )
        ).first()
        tenant_sub_row = (
            await conn.execute(
                text(
                    "SELECT sp.key, ts.status FROM tenant_subscriptions ts "
                    "JOIN subscription_plans sp ON sp.id = ts.plan_id "
                    "WHERE ts.tenant_id = :t"
                ),
                {"t": tenant_id},
            )
        ).first()
        event_row = (
            await conn.execute(
                text("SELECT tenant_id FROM billing_events WHERE stripe_event_id = :e"),
                {"e": "evt_sub_update_1"},
            )
        ).first()
    await engine.dispose()

    assert sub_row.status == "active"
    assert sub_row.stripe_price_id == "price_fake_growth_1"
    assert tenant_sub_row.key == "growth"
    assert tenant_sub_row.status == "active"
    assert str(event_row.tenant_id) == tenant_id


async def test_webhook_is_idempotent_for_a_redelivered_event(client, smtp_capture, monkeypatch):
    _enable_stripe(monkeypatch)
    await _set_plan_stripe_price_id("growth", "price_fake_growth_2")
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="billing-webhook-2@example.com", tenant_name="Idempotent Co"
    )
    tenant_id = await _tenant_id_from_row("billing-webhook-2@example.com")

    event = _build_subscription_event(
        event_id="evt_sub_update_2", tenant_id=tenant_id, price_id="price_fake_growth_2"
    )
    payload_bytes = json.dumps(event).encode()

    for _ in range(2):
        signature = _sign_stripe_payload(payload_bytes, TEST_WEBHOOK_SECRET)
        resp = await client.post(
            "/billing/webhook",
            content=payload_bytes,
            headers={"stripe-signature": signature, "content-type": "application/json"},
        )
        assert resp.status_code == 200, resp.text

    engine = create_async_engine(migrator_asyncpg_url())
    async with engine.begin() as conn:
        count = (
            await conn.execute(
                text("SELECT count(*) FROM billing_events WHERE stripe_event_id = 'evt_sub_update_2'")
            )
        ).scalar_one()
    await engine.dispose()
    assert count == 1


async def test_webhook_subscription_deleted_marks_canceled(client, smtp_capture, monkeypatch):
    _enable_stripe(monkeypatch)
    await _set_plan_stripe_price_id("growth", "price_fake_growth_3")
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="billing-webhook-3@example.com", tenant_name="Cancel Co"
    )
    tenant_id = await _tenant_id_from_row("billing-webhook-3@example.com")

    update_event = _build_subscription_event(
        event_id="evt_sub_update_3", tenant_id=tenant_id, price_id="price_fake_growth_3"
    )
    update_payload = json.dumps(update_event).encode()
    resp = await client.post(
        "/billing/webhook",
        content=update_payload,
        headers={
            "stripe-signature": _sign_stripe_payload(update_payload, TEST_WEBHOOK_SECRET),
            "content-type": "application/json",
        },
    )
    assert resp.status_code == 200, resp.text

    delete_event = {
        "id": "evt_sub_delete_3",
        "object": "event",
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_fake_1",
                "object": "subscription",
                "customer": "cus_fake_webhook_1",
                "status": "canceled",
                "metadata": {"tenant_id": tenant_id},
            }
        },
    }
    delete_payload = json.dumps(delete_event).encode()
    resp2 = await client.post(
        "/billing/webhook",
        content=delete_payload,
        headers={
            "stripe-signature": _sign_stripe_payload(delete_payload, TEST_WEBHOOK_SECRET),
            "content-type": "application/json",
        },
    )
    assert resp2.status_code == 200, resp2.text

    engine = create_async_engine(migrator_asyncpg_url())
    async with engine.begin() as conn:
        tenant_sub_status = (
            await conn.execute(
                text("SELECT status FROM tenant_subscriptions WHERE tenant_id = :t"), {"t": tenant_id}
            )
        ).scalar_one()
        billing_sub_status = (
            await conn.execute(
                text("SELECT status FROM billing_subscriptions WHERE tenant_id = :t"), {"t": tenant_id}
            )
        ).scalar_one()
    await engine.dispose()
    assert tenant_sub_status == "canceled"
    assert billing_sub_status == "canceled"


async def test_webhook_records_paid_invoice(client, smtp_capture, monkeypatch):
    _enable_stripe(monkeypatch)
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="billing-webhook-invoice@example.com", tenant_name="Invoice Co"
    )
    tenant_id = await _tenant_id_from_row("billing-webhook-invoice@example.com")

    now = int(time.time())
    event = {
        "id": "evt_invoice_paid_1",
        "object": "event",
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": "in_fake_1",
                "object": "invoice",
                "customer": "cus_fake_invoice_1",
                "subscription": "sub_fake_1",
                "status": "paid",
                "amount_due": 4900,
                "amount_paid": 4900,
                "currency": "usd",
                "hosted_invoice_url": "https://invoice.stripe.com/fake",
                "invoice_pdf": "https://invoice.stripe.com/fake.pdf",
                "period_start": now,
                "period_end": now + 30 * 24 * 3600,
                "status_transitions": {"paid_at": now},
                "metadata": {"tenant_id": tenant_id},
            }
        },
    }
    payload_bytes = json.dumps(event).encode()
    resp = await client.post(
        "/billing/webhook",
        content=payload_bytes,
        headers={
            "stripe-signature": _sign_stripe_payload(payload_bytes, TEST_WEBHOOK_SECRET),
            "content-type": "application/json",
        },
    )
    assert resp.status_code == 200, resp.text

    engine = create_async_engine(migrator_asyncpg_url())
    async with engine.begin() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT status, amount_due, amount_paid, currency FROM invoice_records "
                    "WHERE stripe_invoice_id = 'in_fake_1'"
                )
            )
        ).first()
    await engine.dispose()
    assert row.status == "paid"
    assert float(row.amount_due) == 49.00
    assert float(row.amount_paid) == 49.00
    assert row.currency == "usd"


async def test_list_invoices_returns_recorded_invoices(client, smtp_capture, monkeypatch):
    _enable_stripe(monkeypatch)
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="billing-list-invoices@example.com", tenant_name="List Invoices Co"
    )
    tenant_id = await _tenant_id_from_row("billing-list-invoices@example.com")

    now = int(time.time())
    event = {
        "id": "evt_invoice_paid_2",
        "object": "event",
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": "in_fake_2",
                "object": "invoice",
                "customer": "cus_fake_invoice_2",
                "subscription": None,
                "status": "paid",
                "amount_due": 1900,
                "amount_paid": 1900,
                "currency": "usd",
                "hosted_invoice_url": None,
                "invoice_pdf": None,
                "period_start": now,
                "period_end": now + 30 * 24 * 3600,
                "status_transitions": {"paid_at": now},
                "metadata": {"tenant_id": tenant_id},
            }
        },
    }
    payload_bytes = json.dumps(event).encode()
    resp = await client.post(
        "/billing/webhook",
        content=payload_bytes,
        headers={
            "stripe-signature": _sign_stripe_payload(payload_bytes, TEST_WEBHOOK_SECRET),
            "content-type": "application/json",
        },
    )
    assert resp.status_code == 200, resp.text

    list_resp = await client.get("/billing/invoices")
    assert list_resp.status_code == 200, list_resp.text
    invoices = list_resp.json()["invoices"]
    assert any(i["stripe_invoice_id"] == "in_fake_2" for i in invoices)


async def test_list_plans_reflects_checkout_availability(client, smtp_capture):
    await _register_owner_and_create_tenant(
        client, smtp_capture, email="billing-plans@example.com", tenant_name="Plans Co"
    )
    await _set_plan_stripe_price_id("trial", "price_fake_trial_for_this_test")
    resp = await client.get("/billing/plans")
    assert resp.status_code == 200, resp.text
    plans = {p["key"]: p for p in resp.json()["plans"]}
    assert "trial" in plans
    assert plans["trial"]["checkout_available"] is True
    assert plans["trial"]["monthly_price_usd"] >= 0
