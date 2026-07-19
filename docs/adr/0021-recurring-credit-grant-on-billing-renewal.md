# ADR-0021: recurring credit grant on billing renewal

## Status
Accepted.

## Context
`SubscriptionPlan.monthly_credit_grant` has existed since Milestone 1's
seed data, but was only ever applied once: `tenancy.services.create_tenant`
grants the trial plan's `monthly_credit_grant` at signup, and nothing
re-grants it on any later billing cycle. `docs/project-status.md` carried
this forward as a known limitation from Milestone 9 onward: "a real
subscription renewing monthly doesn't yet re-grant credits each period...
a webhook-driven grant on `invoice.paid` is natural follow-up work."

No spec text in this session names Milestone 13's scope. It was chosen,
under the user's "Milestone 13" authorization, as the next highest-value
credential-free gap: it needs no live Stripe account (the webhook
*receiver* has always been testable with genuinely-signed synthetic
payloads, per ADR-0017 - no live key required), it closes a real,
long-standing, explicitly-named limitation, and it sits in code already
covered by real signature-verification tests rather than mocked-adapter
tests.

## Decision

### Every paid subscription invoice grants credits, not just renewals
`billing.services._grant_recurring_credits_for_invoice` runs for every
`invoice.paid` event whose invoice carries a `subscription` id (skipping
one-off, non-subscription invoices entirely). It grants the invoiced
price's mapped plan's `monthly_credit_grant`, regardless of whether
Stripe's own `billing_reason` says this is the subscription's first
invoice or a later renewal. This was a deliberate choice, not an
oversight: the tenant's one-time initial grant (Milestone 1) is for the
*trial* plan specifically, made at signup before any real subscription
exists - the first paid invoice for whatever plan a tenant actually checks
out into is a distinct billing period that plan's stipend is genuinely
owed for, exactly like every renewal after it. Treating every paid
subscription invoice uniformly avoids having to special-case
`billing_reason` values (`subscription_create` vs. `subscription_cycle` vs.
`subscription_update` are all real Stripe values with subtly different
semantics) and matches the plan/credit relationship's own simplest,
most defensible reading: "this plan costs this many credits per billing
period, and this invoice represents one billing period, paid."

### The plan is resolved from the invoice's own line item, not the synced subscription row
The invoice's first line item's `price.id` is looked up against
`SubscriptionPlan.stripe_price_id` directly, rather than reading the
already-synced `TenantSubscription.plan_id` (which `_handle_subscription_
event` maintains from `customer.subscription.*` events). Stripe does not
guarantee webhook delivery order between an invoice event and its
sibling subscription event for the same billing cycle - relying on the
subscription row already being in sync would make this grant's
correctness depend on event delivery order, an assumption this codebase
has specifically avoided elsewhere (see `_resolve_tenant_id`'s own
customer-id fallback path for the same reason). Reading the price
directly off the invoice being processed has no such dependency.

### Idempotency: the invoice id, not just the event id
`handle_webhook_event`'s existing `BillingEvent`-id dedup happens *before*
any event-type-specific handler runs, and the `BillingEvent` row recording
that dedup key is only written at the very end of the function, after
every side effect (including this grant) has already run. A crash between
granting credits and that final write would leave nothing to prevent a
genuinely redelivered event - which Stripe's own documentation warns can
arrive under a *different* event id for the same underlying object change
- from granting a second time. `CreditTransaction` is an append-only
ledger with no natural upsert key of its own, unlike `InvoiceRecord`
(unique on `stripe_invoice_id`) or `BillingSubscription` (upserted by
subscription id).

The fix: a new nullable `InvoiceRecord.credit_grant_applied_at` column,
set exactly once per invoice. The grant path re-reads the invoice row
through a new `get_invoice_by_stripe_id_for_update` (`SELECT ... FOR
UPDATE`) immediately before checking and setting this column, inside the
same transaction the grant itself commits in - this closes both the
crash-window gap (the column write and the credit grant are now atomic
with each other) and a genuine concurrent-delivery race (a second request
processing the same invoice blocks on the row lock until the first
transaction commits, then observes the column already set and skips).

### Verified live-idempotency, not just declared
`test_webhook_invoice_paid_redelivered_under_a_different_event_id_does_
not_double_grant` sends two genuinely, correctly HMAC-signed webhook
payloads for the *same* invoice id under two *different* event ids -
reproducing the exact scenario the `BillingEvent`-only guard cannot catch
- against the real test database, and asserts the wallet balance moved
exactly once. This is the specific gap this ADR's idempotency design
exists to close, proven directly rather than only reasoned about.

## Consequences
- New: `apps/api/alembic/versions/7c27453a6ffb_*.py` (adds
  `invoice_records.credit_grant_applied_at`), `docs/adr/0021`.
- Modified: `app/modules/billing/models.py` (`InvoiceRecord.credit_grant_
  applied_at`), `app/modules/billing/repositories.py`
  (`get_invoice_by_stripe_id_for_update`), `app/modules/billing/services.py`
  (`_grant_recurring_credits_for_invoice`, wired into `_handle_invoice_
  event`), `apps/api/tests/test_billing_api.py` (3 new tests).
- Closes `docs/project-status.md`'s "No recurring monthly credit grant is
  wired to the billing cycle" known limitation in full for the standard
  case (a plan with a configured `stripe_price_id` and a positive
  `monthly_credit_grant`).
- Same disclosed gap as the rest of the billing module (ADR-0017): no
  live Stripe account exists in this environment, so this has never been
  exercised against a real Stripe-delivered `invoice.paid` event, only
  against genuinely-signed synthetic ones. The signature-verification
  path and the grant/idempotency logic downstream of it are both real;
  Stripe's own actual invoice/line-item payload shape for every possible
  billing scenario (proration, multiple line items, an invoice item added
  manually alongside the subscription line) has not been observed.
- A multi-line-item invoice (e.g. the subscription's own line item plus a
  manually-added one-off invoice item in the same invoice) is not
  specifically handled - the grant reads only `lines.data[0]`, the first
  line item. For every scenario this codebase's own Checkout Sessions
  produce (a single-price subscription, no add-on line items), this is
  the subscription's own line and is correct; a plan or connector that
  someday adds multiple concurrent line items to one invoice would need
  this revisited to find the *subscription's* line item specifically,
  not just the first one.
