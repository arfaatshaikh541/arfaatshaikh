# ADR-0017: Billing provider integration (Stripe)

## Status
Accepted.

## Context
ADR-0006 deferred a concrete payment/billing provider out of Milestone 1,
explicitly naming the entities it left for later: `BillingCustomer`,
`BillingSubscription`, `BillingEvent`, `InvoiceRecord`, and calling out
"Milestone 9 work." That's the only spec text this session had for this
milestone's scope - there was no other captured requirements text naming
it, so the scope below is read directly off that ADR rather than
inferred from breadcrumbs the way Milestone 8's was.

## Decision

### A real Stripe integration, not a fabricated payment flow
The standing project rule is no fake payment integrations. Stripe's
Python SDK (`stripe`, real, added as a genuine dependency) is used
throughout - real `Customer`, real `checkout.Session`, real
`billing_portal.Session`, real webhook signature verification via
`stripe.Webhook.construct_event`. No code path here simulates a
successful payment or fabricates a subscription state; every state
change is driven by an actual signed event Stripe (or, in this
environment's tests, a payload signed with Stripe's own public HMAC
scheme) sent.

### The webhook is the *sole* source of truth for subscription/invoice state
`create_checkout_session` only ever starts a real Stripe-hosted
Checkout flow and returns its URL - it never itself marks a tenant as
upgraded. The only code path that ever changes `TenantSubscription`'s
plan/status/period, or writes a `BillingSubscription`/`InvoiceRecord`
row, is `handle_webhook_event`, driven by Stripe's own signed
`customer.subscription.*`/`invoice.*` events. A tenant admin closing
the browser mid-checkout, or Stripe silently declining the card after
the success-redirect already fired, must never be able to grant a plan
upgrade this platform never actually confirmed - the redirect is a UX
convenience, not an authorization signal.

### `TenantSubscription` stays the one row entitlements resolve from; four new tables make its sync observable
Milestone 1's `TenantSubscription`/`resolve_entitlements` machinery is
untouched in shape - still exactly one row per tenant, mutated in
place. What's new is *what drives that mutation*: previously only ever
set once by seed data at tenant creation, it's now also updated by
`subscriptions.repositories.update_tenant_subscription_plan` from the
webhook handler. `BillingCustomer` (tenant <-> Stripe Customer
mapping), `BillingSubscription` (a live mirror of Stripe's own
subscription object, in Stripe's own status vocabulary - deliberately
*not* normalized to `TenantSubscription`'s simpler
"active"/anything-else scheme, so the real state is never lost to that
simplification), `BillingEvent` (every webhook event received, keyed by
Stripe's event id), and `InvoiceRecord` (one row per invoice) are what
make that sync auditable rather than a black box.

### `SubscriptionPlan.stripe_price_id`: real, per-deployment configuration, never fabricated
No real Stripe account exists in this environment (see "What was not
verified" below), so there is no real Price id this codebase could
honestly hardcode. `stripe_price_id` is a new, nullable column on the
existing `SubscriptionPlan` catalog row - NULL in seed data, exactly as
honest as leaving it unset. `create_checkout_session` checks it and
fails with a clear `ConflictError` ("no Stripe price configured yet")
rather than either fabricating a fake price id or silently proceeding
with a broken checkout - the same discipline ADR-0015 established for a
missing S3 bucket: a real configuration gap surfaces as a clear error,
never masked by a "helpful" fallback. The frontend's plan cards read
this state directly (`checkout_available`) and show "Not yet available"
instead of an "Upgrade" button for any plan without a real price
configured, rather than letting a click reach the API only to fail.

### Idempotency and RLS: the same patterns already established, applied to a new kind of caller
Stripe redelivers webhook events at-least-once, exactly like this
codebase's own Celery tasks - `BillingEvent.stripe_event_id`'s
uniqueness makes a redelivery a no-op rather than double-applying a
state change. The webhook route is the first HTTP endpoint in this
codebase to have no session-cookie-derived tenant at request time (it's
a server-to-server call from Stripe, authenticated by its own HMAC
signature, not this platform's session/CSRF machinery); it resolves the
tenant from a unique external key (the Stripe customer/event id) via
`set_platform_bypass`, then writes with that tenant_id column always
correctly set - the same "narrowly-scoped, unique-key lookup" pattern
ADR-0007 already sanctions for invitation-accept-by-token and the
worker's own task lookups, applied here to a new class of caller.
`BillingEvent.tenant_id` is nullable for the (should be rare) case of an
event for a Stripe object this platform never linked to a tenant (e.g.
one created directly in a Stripe dashboard) - such a row is simply
invisible under RLS to every tenant and only readable under
platform_bypass, which is the correct behavior for something that isn't
actually that tenant's data.

### Permissions: reuses the Milestone 1 catalog exactly as declared
`billing.manage` gates starting a checkout or opening the Customer
Portal; `billing.view` gates listing plans/invoices/the current
subscription. Both were already seeded in Milestone 1 - along with a
"Billing Manager" role that has both - unused until now. No new
permission was needed.

### `GET /billing/plans`: new, minimal, and necessary
Nothing in the existing API let a tenant see what plans exist to
upgrade to. A small new endpoint (gated by the existing `billing.view`)
lists active plans with `checkout_available` reflecting whether a real
Stripe price is configured - the minimum needed for the frontend to
offer real upgrade options without the client ever guessing or
hardcoding what's available.

### What was not verified: no real Stripe account exists in this environment
The same disclosure pattern as ADR-0010 (Google Places) and ADR-0016
(the webhook delivery gap): no Stripe API key, webhook secret, or Price
ids exist here, so no live Checkout Session was ever actually opened
against Stripe's real servers, and no real webhook was ever delivered
by Stripe itself. What *is* verified for real, without needing a live
key: **webhook signature verification** - Stripe's HMAC-SHA256 scheme
is fully public, so every webhook test in `test_billing_api.py`
constructs a genuinely, correctly signed payload and posts it through
the real `stripe.Webhook.construct_event` verification path, not a
bypassed one; and **the exact shape of every outbound Stripe SDK call**
(`Customer.create_async`, `checkout.Session.create_async`,
`billing_portal.Session.create_async`), verified by asserting on the
captured call arguments after monkeypatching the SDK call boundary -
the same "mocked-adapter" discipline ADR-0010 established. Live browser
verification (Playwright, against the real running stack with real
Postgres/Redis/SMTP) confirmed the full UI flow - plan cards correctly
showing "Upgrade" only for a plan with a real price configured versus
"Not yet available" for the rest, and the honest "Billing is not
configured for this deployment" error banner surfacing correctly when a
configured plan's checkout is attempted with no `STRIPE_SECRET_KEY` set.
**Before relying on this in production**: create a real Stripe account,
set `STRIPE_SECRET_KEY`/`STRIPE_PUBLISHABLE_KEY`/`STRIPE_WEBHOOK_SECRET`,
create real Products/Prices in Stripe and set each `SubscriptionPlan.
stripe_price_id` to match, configure the webhook endpoint in the Stripe
dashboard to point at `/billing/webhook`, and run one real checkout
end-to-end as a smoke test before pointing a real tenant at it.

## Consequences
- New backend module `app.modules.billing` (`models.py`:
  `BillingCustomer`, `BillingSubscription`, `BillingEvent`,
  `InvoiceRecord`; `repositories.py`; `services.py` - checkout/portal
  session creation, webhook event handling; `schemas.py`; `routes.py`),
  its own RLS-protected migration, and a new `stripe_price_id` column on
  `SubscriptionPlan`.
- `app.modules.subscriptions.repositories` gained
  `get_subscription_for_tenant`/`update_tenant_subscription_plan`
  (mutating the tenant's one subscription row in place - previously
  only ever created once, never updated) and
  `get_plan_by_stripe_price_id`/`list_active_plans`.
- New config: `stripe_secret_key`/`stripe_publishable_key`/
  `stripe_webhook_secret`/`billing_portal_return_url`/
  `billing_checkout_success_url`/`billing_checkout_cancel_url` - all
  empty/localhost defaults, the same "nothing fabricates a working
  integration without real credentials" pattern `google_places_api_key`
  and `credential_encryption_master_key` already established.
- New frontend: the existing `/usage` page (already titled "Usage &
  Billing") gained a plan-comparison grid with real upgrade-availability
  state, a "Manage billing" button opening the real Customer Portal, and
  an invoice history table - deliberately not a new nav item/page, since
  billing already had a natural home there.
- No credit-charging change: subscribing/upgrading itself is not a
  credit-metered action (it's what *grants* credits, via each plan's
  `monthly_credit_grant` - unchanged, still seed-data-driven; wiring an
  actual monthly credit grant to a real billing cycle is not in this
  milestone's scope, since ADR-0006/the captured build list never
  specified a recurring-grant trigger mechanism).
