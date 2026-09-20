# Financial Control Architecture

## Core rule

**No LLM or agent ever holds unrestricted banking credentials.** Financial capability is
built as a layered system where the model's role is preparation and analysis, and actual
money movement passes through deterministic, hard-limit enforcement that does not trust
the model's arithmetic or judgment as the final control.

## Layers

1. **Read-only monitoring by default** — bank/payment-processor/accounting connectors are
   provisioned read-only unless a specific write capability is explicitly authorized.
2. **Transaction preparation** — agents (Financial Analyst, Invoice Assistant) can
   *prepare* a payment, invoice, or transfer as a draft record with full detail, but
   preparation alone has no effect on real funds.
3. **Budget envelopes** — every spend-capable goal/campaign carries a hard budget
   envelope enforced at the payment credential/connector layer (e.g., the ad platform
   API token itself is provisioned with a spend cap where the platform supports it;
   otherwise a pre-spend balance check gates every transaction request at the Action
   Broker).
4. **Merchant/recipient restrictions** — payment actions are restricted to an
   owner-approved allowlist of merchants/recipients for autonomous execution; a new
   payee is RED by default (mirrors "bank changes" in the RED examples).
5. **Amount limits** — per-transaction and per-period (daily/weekly/monthly) caps, set by
   the owner, enforced by the Policy Engine and checked by the Action Broker before the
   Credential Broker issues any payment-capable token.
6. **Velocity limits** — rate limits on transaction frequency to catch a runaway loop or
   compromised-agent scenario before it can drain a budget in a burst (failure scenario
   #37).
7. **Anomaly detection** — the Security Guardian watches spending patterns independent
   of the Financial Analyst's own reporting (an agent cannot mark its own spending as
   "normal").
8. **Dual authorization for critical actions** — anything RED-tier (large transfers, new
   bank relationships, contract-bound financial commitments) requires two distinct
   authorization factors: owner approval through the Control Plane *and* the
   transaction's own policy checks, not either alone.

## Reconciliation

A Reconciliation Assistant cross-checks AURA-reported financial figures (revenue,
expenses, pipeline value) against the actual source-of-truth accounting/payment system
before those figures appear in executive reports — preventing reported metrics from
silently diverging from reality (failure scenario #44).

## Explicit non-goals for Milestone 0+

Full autonomous payment execution (Level 4/5 on RED financial actions) is **not** in
scope for early milestones regardless of how much track record accumulates, absent a
separately designed and owner-approved narrow mechanism (e.g., "auto-pay recurring
vendor invoices under AED 200 to a pre-approved vendor list" could later be scoped as a
tightly-bounded Level 4 exception — but this requires its own design review, not a
default unlock).
