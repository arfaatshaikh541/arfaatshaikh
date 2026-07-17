# ADR-0006: No billing provider selected yet

## Status
Accepted (Milestone 1 approval item #8).

## Decision
Milestone 1 builds the subscription/entitlement/credit-ledger data model
and services (`subscription_plans`, `features`, `plan_features`,
`tenant_subscriptions`, `credit_wallets`, `credit_transactions`,
`credit_reservations`) and a `billing.view` / `billing.manage` permission
pair, but does not integrate a concrete payment/billing provider (e.g.
Stripe). The `BillingCustomer`, `BillingSubscription`, `BillingEvent`,
`InvoiceRecord` entities from the full architecture are Milestone 9 work.

## Consequences
- Seed data creates fictional `trial` / `starter` / `growth` / `scale`
  plans directly in the database; there is no real payment flow.
- `/billing/subscription` returns whatever `TenantSubscription` row exists
  for the tenant (seeded as `trial` for every new tenant) - there is no
  upgrade/downgrade/cancel endpoint yet.
