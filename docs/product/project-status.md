# Project status

**Current milestone:** Milestone 6 — Proposals
**Status:** Complete, verified against a real PostgreSQL + Redis stack. Awaiting your review before starting Milestone 7.
**Last updated:** 2026-07-15

---

## What was built (Milestone 6)

### Backend (`apps/api`)
- **New `proposals` module**: `ProposalTemplate` + `ProposalTemplateLineItem` (reusable defaults — name, description, terms, line items), `Proposal` (the client-facing document — lead, optional template, title, status, currency, tax rate, terms, optional expiry, the full send/view/accept/reject lifecycle timestamps, and the public acceptance token), `ProposalLineItem` (the actual line items on a specific proposal, independent of its originating template so editing one never mutates the other).
- **Status lifecycle**: `DRAFT → SENT → VIEWED → ACCEPTED | REJECTED`, plus `EXPIRED` (checked against `valid_until` at accept time). Line items are only editable while `DRAFT`; `send_proposal` generates the public token (idempotently — resending doesn't rotate an existing token) and is itself idempotent from `DRAFT` or already-`SENT`.
- **Totals computed on-the-fly, never stored**: `proposals.service.compute_totals` derives subtotal/tax/total from live line items on every read — a deliberate choice to avoid a stored total ever drifting out of sync with the line items it's derived from, consistent with how this codebase avoids denormalized/cached derived state elsewhere.
- **Public acceptance surface** (`/public/proposals/{token}`, `.../accept`, `.../reject`) reusing the exact raw-token/no-RLS pattern already proven for `TenantCaptureToken`: an unguessable 32-byte token is the sole authorization proof, looked up directly with no tenant filter (the `proposals` table itself is deliberately excluded from row-level security — see `docs/database/README.md` for the full reasoning), then `set_rls_context` is called explicitly before touching any other tenant-owned table. **Deliberately not gated by the `proposals` module entitlement**, unlike every other public flow in this codebase — a client must never be blocked from responding to a proposal they already received just because the tenant's subscription changed after it was sent. Verified live: disabling the module for a tenant made `GET /tenant/proposals` return 403 while the public accept route kept returning 200.
- **Three new `EmailTriggerEvent` values** (`proposal_sent`, `proposal_accepted`, `proposal_rejected`) and **two new `WorkflowTriggerEvent` values** (`proposal_accepted`, `proposal_rejected`) — both columns were already widened to `VARCHAR(30)` in Milestone 4, so no further width migration was needed, only the Python-side enum additions.
- **No new permissions needed.** `proposals.view`/`proposals.manage` and the `proposals` module (with its boolean `proposals` feature, no usage-limit metric) were already provisioned in the Milestone 1 catalog — the fifth catalog entry in a row (after communications, booking, workflow automation) that the original commercial-model design anticipated correctly. Notably, `Manager` is granted `proposals.manage` (unlike `workflows.manage`, which is Administrator-only) — a real Milestone 1 catalog design choice, not a Milestone 6 change: sending a quote is treated as routine manager-level work, configuring automation is not.
- **Extended the Engagement Operations seed template** with three proposal email templates (sent/accepted/rejected) and a "Standard Engagement Proposal" template with two default line items — applied to every newly created tenant.
- **Two new Alembic migrations** (schema + RLS), exercised through a full upgrade → downgrade → re-upgrade cycle. The RLS migration covers `proposal_templates`, `proposal_template_line_items`, and `proposal_line_items` only — `proposals` is intentionally excluded, documented in the migration docstring and in `docs/database/README.md`.
- **12 new pytest tests** (109 total with Milestones 1–5's), covering: template creation with line items, totals computation from a template (with tax) and from explicit line items, draft-only line-item editing, send generating a token and dispatching the `proposal_sent` email, a public view flipping the proposal to `viewed` (idempotently), public accept dispatching the `proposal_accepted` email and triggering a `workflow_automation` run, public reject recording a reason, an expired proposal rejecting an accept attempt, the module-entitlement exception for the public routes, Sales-Agent-can-view-but-not-manage permission enforcement, and cross-tenant isolation.

### Frontend (`apps/web`)
- `/proposal-templates` — create/list/delete templates with an inline dynamic line-item editor.
- `/proposals` — list (optionally filtered by `?leadId=`), create-proposal form (lead picker, optional template, tax rate, optional expiry).
- `/proposals/[proposalId]` — detail view: editable line items while draft, computed subtotal/tax/total, Send action, the client-facing link once sent, and the accepted/rejected outcome banner.
- `/proposals/view/[token]` — the public, unauthenticated acceptance page: line items, totals, terms, and Accept (with a required name) / Decline (with an optional reason) actions, each showing a final-state banner once responded to.
- Lead detail page gained a "Proposals" section (mirroring the Milestone 4 Appointments section) linking into the filtered `/proposals` list and each proposal's detail page.
- Sidebar nav gained Proposals (`proposals.view`) and Proposal Templates (`proposals.manage`), both gated by the `proposals` module entitlement.

### Tests & verification
- `ruff check app` — 0 errors. `pytest -q` — 109 passed. `eslint` — 0 errors. `tsc --noEmit` — 0 errors. `next build` — succeeds, 34 routes. `vitest run` — 4 passed.
- Both new Alembic migrations exercised through a full upgrade → downgrade → re-upgrade cycle against real Postgres, against both the dev (`cops`) and test (`cops_test`) databases.
- Manually smoke-tested over real HTTP against a freshly seeded demo tenant with the API server actually running: confirmed the seeded "Standard Engagement Proposal" template via `GET`; created a proposal from it and confirmed the copied line items and computed totals (2000 + 5% tax = 2100 AED); sent it and confirmed a public token was generated and an `email_delivery_logs` row was written with correctly merge-field-rendered subject/body (delivery itself reported `FAILED` only because no real SMTP server is configured in this sandbox, the same expected/documented limitation as every prior milestone); fetched the public page unauthenticated and confirmed it flipped `sent → viewed`; accepted it unauthenticated and confirmed `accepted_by_name`/`accepted_at` were recorded and `proposal.accepted` was written to `audit_logs`; disabled the `proposals` module for the tenant via `grant_feature_override` and confirmed `GET /tenant/proposals` returned 403 while a second proposal's public accept link still returned 200 — the full lifecycle and the module-entitlement exception both verified live, not just inside the test suite.

## Acceptance criteria — verified

| Criterion (from your Milestone 6 spec) | Verified how |
|---|---|
| Proposal templates with reusable line items | `ProposalTemplate`/`ProposalTemplateLineItem` models; template line items copy into a new proposal's own `ProposalLineItem` rows, independently editable afterward |
| Client acceptance flow | Public, unauthenticated, unguessable-token acceptance page with Accept/Reject actions; state-machine guards prevent replaying an accept/reject on an already-final proposal |
| Building on the lead/communications/workflow primitives | `send_proposal`/accept/reject dispatch through Milestone 3's `send_templated_email` (new trigger events) and Milestone 5's `evaluate_triggers_for_lead` (new trigger events); every proposal is anchored to a `Lead` |
| Explainable / auditable | Every send/accept/reject writes an `audit_logs` row and a `crm` activity-timeline entry (visible on the lead detail page) |
| Entitlement enforcement (with the one deliberate exception) | `proposals` module checked on every authenticated route via `require_module("proposals")`; explicitly and deliberately *not* checked on the public accept/reject routes, documented in both this doc and `docs/security/README.md` |

## Known limitations

1. **No malware/virus scanning or attachment support on proposals** — proposals are structured line items only in this milestone, not file attachments; reserved for Milestone 7 (document collection), which already has a dedicated malware-scanning integration point flagged.
2. **No proposal versioning or revision history.** Editing a draft's line items overwrites them in place; once sent, line items are locked (enforced by the service layer) but there's no "resend a revised copy" workflow yet — resending currently just re-dispatches the same content and reuses the existing token. If a genuinely revised proposal is needed today, the practical workaround is creating a new proposal.
3. **`proposals` itself is excluded from PostgreSQL row-level security**, unlike every other tenant-owned business table — a deliberate, documented tradeoff (see `docs/database/README.md`'s row-level security summary and the RLS migration's docstring) to support the public token lookup before any tenant context exists, mirroring the precedent already set by `tenant_capture_tokens`. Every `ProposalRepository` method still filters explicitly by `tenant_id` at the application layer, but this table has one less layer of defense-in-depth than the rest of the schema. Its child table `proposal_line_items` remains fully row-level-secured.
4. **No PDF export or e-signature integration** — the public acceptance page is a rendered web page, not a downloadable/signable document; "Accept" records a typed name as consent, not a cryptographic signature. Flagged as a candidate for a later integrations milestone if a formal e-signature audit trail becomes a requirement.
5. **Same environment caveats as Milestones 1–5 carry forward**: Docker Compose itself was not run end-to-end in this sandbox; all verification used the same application code run directly against local PostgreSQL 16 + Redis 7, including a real running `uvicorn` instance for the live HTTP smoke test. No real SMTP server is configured, so email delivery genuinely reports `FAILED` in `email_delivery_logs` even though the merge-field rendering and dispatch logic themselves are verified correct. No browser was available to visually confirm the new UI.

## Pending decisions

None new this milestone — Milestone 1's pending decisions (tenant-URL routing, production email/storage provider choice) remain open and don't block Milestone 7.

## Next action

Awaiting your review of Milestone 6. To proceed, reply exactly: **APPROVE MILESTONE 7**

Milestone 7 (per the approved architecture) is Client Onboarding and
Document Collection — onboarding templates/cases and secure document
upload/review, the next stage in the lead-to-client lifecycle after a
proposal is accepted.
