"""Real Stripe integration: Checkout Sessions to subscribe/upgrade,
Customer Portal sessions for self-service management/cancellation, and a
webhook handler that is the *sole* source of truth for subscription/
invoice state.

Deliberately never trusts a client-completed checkout redirect to mean
the subscription actually changed - `create_checkout_session` only ever
starts a real Stripe-hosted flow; every actual entitlement/plan change
happens in `handle_webhook_event`, driven by Stripe's own signed
`customer.subscription.*` events. A tenant admin closing the browser tab
mid-checkout, or Stripe silently declining the card after the redirect
already fired, must never be able to grant a plan upgrade this platform
never actually confirmed.
"""

import uuid
from datetime import UTC, datetime

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, ResourceNotFoundError, ValidationAppError
from app.core.logging import get_logger
from app.modules.billing import repositories as billing_repo
from app.modules.identity.repositories import get_user_by_id
from app.modules.subscriptions import repositories as subscriptions_repo
from app.modules.tenancy.repositories import get_tenant_by_id

logger = get_logger("gridkeep.billing")

# Stripe subscription statuses that still mean "this tenant's entitlements
# should resolve as if the plan is active" - trialing is included since a
# trial is a real, currently-usable subscription state, not a lapse.
_STRIPE_STATUSES_MEANING_ACTIVE = {"active", "trialing"}


def _require_stripe_configured() -> str:
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise ConflictError(
            "Billing is not configured for this deployment (no Stripe secret key set)."
        )
    return settings.stripe_secret_key


async def get_or_create_billing_customer(
    session: AsyncSession, *, tenant_id: uuid.UUID, requesting_user_id: uuid.UUID
):
    existing = await billing_repo.get_billing_customer_for_tenant(session, tenant_id)
    if existing is not None:
        return existing

    api_key = _require_stripe_configured()
    tenant = await get_tenant_by_id(session, tenant_id)
    if tenant is None:
        raise ResourceNotFoundError("Tenant not found.")
    user = await get_user_by_id(session, requesting_user_id)

    customer_params: dict = {
        "api_key": api_key,
        "name": tenant.name,
        "metadata": {"tenant_id": str(tenant_id)},
    }
    if user is not None:
        customer_params["email"] = user.email
    stripe_customer = await stripe.Customer.create_async(**customer_params)
    return await billing_repo.create_billing_customer(
        session, tenant_id=tenant_id, stripe_customer_id=stripe_customer.id
    )


async def create_checkout_session(
    session: AsyncSession, *, tenant_id: uuid.UUID, requesting_user_id: uuid.UUID, plan_key: str
) -> str:
    api_key = _require_stripe_configured()
    settings = get_settings()

    plan = await subscriptions_repo.get_plan_by_key(session, plan_key)
    if plan is None:
        raise ResourceNotFoundError(f"Unknown plan: {plan_key!r}.")
    if not plan.stripe_price_id:
        # Real, honest failure rather than a fabricated checkout - see
        # SubscriptionPlan.stripe_price_id's own docstring and ADR-0017.
        raise ConflictError(
            f"Plan {plan_key!r} has no Stripe price configured yet. "
            "An operator must set SubscriptionPlan.stripe_price_id from a real Stripe "
            "account before tenants can check out for this plan."
        )

    customer = await get_or_create_billing_customer(
        session, tenant_id=tenant_id, requesting_user_id=requesting_user_id
    )

    checkout_session = await stripe.checkout.Session.create_async(
        api_key=api_key,
        mode="subscription",
        customer=customer.stripe_customer_id,
        line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
        success_url=settings.billing_checkout_success_url,
        cancel_url=settings.billing_checkout_cancel_url,
        client_reference_id=str(tenant_id),
        metadata={"tenant_id": str(tenant_id), "plan_key": plan_key},
    )
    if checkout_session.url is None:
        raise ConflictError("Stripe did not return a checkout URL.")
    return checkout_session.url


async def create_portal_session(
    session: AsyncSession, *, tenant_id: uuid.UUID, requesting_user_id: uuid.UUID
) -> str:
    api_key = _require_stripe_configured()
    settings = get_settings()

    customer = await billing_repo.get_billing_customer_for_tenant(session, tenant_id)
    if customer is None:
        raise ConflictError("This tenant has no billing customer yet - subscribe to a plan first.")

    portal_session = await stripe.billing_portal.Session.create_async(
        api_key=api_key,
        customer=customer.stripe_customer_id,
        return_url=settings.billing_portal_return_url,
    )
    return portal_session.url


def _from_unix(ts: int | None) -> datetime | None:
    return datetime.fromtimestamp(ts, tz=UTC) if ts is not None else None


def _require_unix(ts: int | None) -> datetime:
    """For fields Stripe's own API contract guarantees are always present
    on a real subscription object (current_period_start/end) - a missing
    value here would mean Stripe's response shape genuinely changed, which
    should fail loudly rather than silently store a fabricated timestamp."""
    if ts is None:
        raise ValueError("Expected a Stripe subscription period timestamp, got None.")
    return datetime.fromtimestamp(ts, tz=UTC)


async def _sync_tenant_subscription_from_stripe(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    stripe_price_id: str,
    stripe_status: str,
    current_period_start: datetime,
    current_period_end: datetime,
) -> None:
    plan = await subscriptions_repo.get_plan_by_stripe_price_id(session, stripe_price_id)
    if plan is None:
        # A subscription for a price this platform's catalog doesn't
        # recognize (e.g. created directly in the Stripe dashboard, or a
        # price added to Stripe but not yet mapped to a SubscriptionPlan
        # here) - never fabricate a plan assignment for it. The real
        # BillingSubscription row is still recorded by the caller; only
        # the TenantSubscription/entitlement sync is skipped.
        logger.warning(
            "billing_webhook_unmapped_price",
            tenant_id=str(tenant_id),
            stripe_price_id=stripe_price_id,
        )
        return

    normalized_status = (
        "active" if stripe_status in _STRIPE_STATUSES_MEANING_ACTIVE else stripe_status
    )
    tenant_subscription = await subscriptions_repo.get_subscription_for_tenant(session, tenant_id)
    if tenant_subscription is None:
        # Every tenant gets one TenantSubscription row at creation (see
        # app.modules.tenancy.services) - this would mean that row was
        # somehow deleted, not a normal state. Recorded, not silently
        # fabricated back into existence.
        logger.warning("billing_webhook_no_tenant_subscription_row", tenant_id=str(tenant_id))
        return

    await subscriptions_repo.update_tenant_subscription_plan(
        session,
        tenant_subscription,
        plan_id=plan.id,
        status=normalized_status,
        current_period_start=current_period_start,
        current_period_end=current_period_end,
    )


async def handle_webhook_event(
    session: AsyncSession, *, payload: bytes, signature_header: str
) -> None:
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise ConflictError("Stripe webhook secret is not configured for this deployment.")

    try:
        event = stripe.Webhook.construct_event(
            payload, signature_header, settings.stripe_webhook_secret
        )
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise ValidationAppError(f"Invalid Stripe webhook payload or signature: {exc}") from exc

    # Idempotency: Stripe redelivers events (at-least-once, same as this
    # codebase's own Celery tasks); a redelivered event id is a no-op,
    # not reprocessed - same discipline as every worker task's
    # duplicate-delivery guard (see ADR-0007/ADR-0009's neighbors).
    existing = await billing_repo.get_billing_event_by_stripe_id(session, event.id)
    if existing is not None:
        return

    # Converted to a plain dict immediately - `StripeObject` supports `[]`
    # access but not a dict's `.get()`, and working with a real dict here
    # avoids relying on exactly which StripeObject methods exist across
    # SDK versions. `event.to_dict()` (used for `payload` below) already
    # recurses through nested StripeObjects the same way.
    obj = event.data.object.to_dict()
    event_dict = event.to_dict()
    tenant_id = _resolve_tenant_id(obj)
    if tenant_id is None:
        customer_id = obj.get("customer")
        if customer_id:
            customer = await billing_repo.get_billing_customer_by_stripe_id(session, customer_id)
            if customer is not None:
                tenant_id = customer.tenant_id

    if event.type in ("customer.subscription.created", "customer.subscription.updated"):
        await _handle_subscription_event(session, obj, tenant_id)
    elif event.type == "customer.subscription.deleted":
        await _handle_subscription_deleted(session, obj, tenant_id)
    elif event.type in ("invoice.paid", "invoice.payment_failed", "invoice.finalized"):
        await _handle_invoice_event(session, obj, tenant_id)
    # checkout.session.completed and any other event type are still
    # recorded below (the full audit trail), just with no further side
    # effect - the subscription.* events already carry the real state.

    await billing_repo.create_billing_event(
        session,
        tenant_id=tenant_id,
        stripe_event_id=event.id,
        event_type=event.type,
        processed_at=datetime.now(UTC),
        payload=event_dict,
    )


def _resolve_tenant_id(obj: dict) -> uuid.UUID | None:
    metadata = obj.get("metadata") or {}
    raw = metadata.get("tenant_id")
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


async def _handle_subscription_event(
    session: AsyncSession, subscription: dict, tenant_id: uuid.UUID | None
) -> None:
    if tenant_id is None:
        logger.warning(
            "billing_webhook_subscription_event_unresolved_tenant",
            stripe_subscription_id=subscription["id"],
        )
        return
    price_id = subscription["items"]["data"][0]["price"]["id"]
    period_start = _require_unix(subscription["current_period_start"])
    period_end = _require_unix(subscription["current_period_end"])
    await billing_repo.upsert_billing_subscription(
        session,
        tenant_id=tenant_id,
        stripe_subscription_id=subscription["id"],
        stripe_customer_id=subscription["customer"],
        stripe_price_id=price_id,
        status=subscription["status"],
        current_period_start=period_start,
        current_period_end=period_end,
        cancel_at_period_end=bool(subscription["cancel_at_period_end"]),
    )
    await _sync_tenant_subscription_from_stripe(
        session,
        tenant_id=tenant_id,
        stripe_price_id=price_id,
        stripe_status=subscription["status"],
        current_period_start=period_start,
        current_period_end=period_end,
    )


async def _handle_subscription_deleted(
    session: AsyncSession, subscription: dict, tenant_id: uuid.UUID | None
) -> None:
    if tenant_id is None:
        logger.warning(
            "billing_webhook_subscription_deleted_unresolved_tenant",
            stripe_subscription_id=subscription["id"],
        )
        return
    billing_subscription = await billing_repo.get_billing_subscription_for_tenant(
        session, tenant_id
    )
    if billing_subscription is not None:
        billing_subscription.status = "canceled"
        await session.flush()
    tenant_subscription = await subscriptions_repo.get_subscription_for_tenant(session, tenant_id)
    if tenant_subscription is not None:
        # Never delete the row or fabricate a fallback plan - just record
        # that entitlements should no longer resolve as active.
        tenant_subscription.status = "canceled"
        await session.flush()


async def _handle_invoice_event(
    session: AsyncSession, invoice: dict, tenant_id: uuid.UUID | None
) -> None:
    if tenant_id is None:
        logger.warning(
            "billing_webhook_invoice_event_unresolved_tenant", stripe_invoice_id=invoice["id"]
        )
        return
    status_transitions = invoice.get("status_transitions") or {}
    paid_at_ts = status_transitions.get("paid_at")
    await billing_repo.upsert_invoice_record(
        session,
        tenant_id=tenant_id,
        stripe_invoice_id=invoice["id"],
        stripe_subscription_id=invoice.get("subscription"),
        status=invoice["status"],
        amount_due=invoice["amount_due"] / 100,
        amount_paid=invoice["amount_paid"] / 100,
        currency=invoice["currency"],
        hosted_invoice_url=invoice.get("hosted_invoice_url"),
        invoice_pdf_url=invoice.get("invoice_pdf"),
        period_start=_from_unix(invoice.get("period_start")),
        period_end=_from_unix(invoice.get("period_end")),
        paid_at=_from_unix(paid_at_ts),
    )
