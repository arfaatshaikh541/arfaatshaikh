# Project status

**Current milestone:** Milestone 8 — Client Portal and Deadlines
**Status:** Complete, verified against a real PostgreSQL + Redis stack. Awaiting your review before starting Milestone 9.
**Last updated:** 2026-07-15

---

## What was built (Milestone 8)

This milestone adds the first client-facing *authenticated* surface in
the platform — a self-service login distinct from every prior public
per-request token link — plus compliance/service **deadline** tracking,
the natural next stage after a client has been onboarded (Milestone 7).

Before writing any code, two decisions were escalated to you via
`AskUserQuestion` rather than made unilaterally, given how
security-critical authentication is: **password + explicit staff
invitation** (over magic links) for the login mechanism, and **staff
invites explicitly** (over auto-granting access on some trigger) for how
a lead gets portal access in the first place. Both were confirmed as
"Recommended" and implemented as chosen.

### Backend (`apps/api`)
- **New `deadlines` module**: `Deadline` (title, description, due date, `OPEN`/`COMPLETED` status, optional `recurrence_interval_days`, `reminder_sent_at`). Completing a recurring deadline automatically creates the next occurrence (`due_date + recurrence_interval_days`); completing an already-completed deadline is rejected. A daily Celery beat sweep (`send_deadline_reminders`, 08:00, a deliberate deviation from the platform's usual 15-minute cadence since deadlines are date-granularity, not time-granularity) emails leads whose deadline falls within a 7-day lead window, and marks `reminder_sent_at` unconditionally — even for a lead with no email — so a sweep never reprocesses the same deadline. Verified live and by automated test that the reminder fires exactly once per occurrence.
- **New `portal` module — a second, fully separate authentication domain**: `PortalAccount`, `PortalInvitation`, `PortalSession`, `PortalPasswordResetToken`, mirroring the `identity` module's `User`/`Membership`/`Invitation`/`Session`/`PasswordResetToken` pattern exactly, but scoped per-*lead* rather than per-staff-user. Reuses the same Argon2id password hashing and opaque/hashed session token design as staff auth — no separate, unaudited crypto.
- **A genuine architectural bug caught and fixed before any test ran**: because `PortalAccount` lives in a row-level-secured table, a token/session row that must be looked up *before* any tenant context exists (an unauthenticated login or password-reset request) can't `SELECT` it — RLS fails closed. Fixed by giving `PortalSession` and `PortalPasswordResetToken` their own denormalized `tenant_id` column (extending the precedent `Invitation.tenant_id` already set), so RLS context can be established from the token row itself before it ever touches `portal_accounts`. Documented in both the model docstrings and `docs/database/README.md`.
- **Tenant-slug-scoped client login** (`/portal/{tenantSlug}/login`): since a portal account's email is unique only *within* a tenant (unlike staff `User.email`, which is global), a new `tenancy.service.get_tenant_by_slug` bootstrap resolves the tenant from the URL under a transient platform-admin RLS bypass, then re-scopes to it before any credential check.
- **A separate portal session cookie** (`cops_portal_session`), coexisting with staff's `cops_session` in the same browser without collision.
- **Per-request module gating on every portal route** — a third, deliberately different entitlement-gating choice from Milestones 6 and 7: a proposal accept/reject is a one-time transaction (never gated); a document upload has an ongoing storage cost (gated only at upload time); the portal itself is an ongoing feature grant, so `client_portal` is checked on *every* request via the `get_portal_auth_context` dependency, including `/me`. Verified live: disabling the module 403'd every portal route, including an already-authenticated session's `/me`; re-enabling immediately restored 200.
- **Cross-lead authorization boundary**: `_assert_belongs_to_lead` in `portal/routes.py` checks every proposal/document-request/onboarding-case/appointment/deadline against the caller's own `lead_id` before returning or acting on it, raising 404 (never 403) on a mismatch so a portal account can't learn another lead's resource even exists. Verified live.
- **Portal content routes are thin composition, not new business logic** — they call the existing `proposals.service.accept_proposal`/`reject_proposal`, `documents.service.upload_document`, `onboarding.service.list_cases_for_lead`, `booking.service.list_appointments`, and `deadlines.service.list_deadlines_for_lead` directly, scoped to the caller's own lead.
- **Staff-facing portal management** (`/tenant/portal-accounts`, `portal.manage` permission): list, invite (rejects a lead with no email, and a lead that already has an account), and revoke (which immediately revokes all of that account's sessions).
- **Zero new permission codes needed** — unlike Milestone 7's one-off gap, Milestone 1's original permission catalog had already correctly pre-provisioned both `portal.manage` (Administrator + Support Agent, not Manager) and `deadlines.manage` (Administrator + Manager + Support Agent, not Sales Agent/Viewer) with the right role scoping.
- **One new `EmailTriggerEvent`** (`deadline_upcoming`) wired the same way every prior milestone's trigger events were — the column was already wide enough, no migration needed.
- **Two new Alembic migrations** (schema + RLS), exercised through a full upgrade → downgrade → re-upgrade cycle against both the dev and test databases. `deadlines` and `portal_accounts` are row-level-secured normally; `portal_invitations`, `portal_sessions`, and `portal_password_reset_tokens` are deliberately excluded (same reasoning as `invitations`/`sessions` in the staff auth system, extended with the denormalized-`tenant_id` bootstrap technique described above).
- **Extended the Engagement Operations seed template** with a "Deadline Reminder" email template, applied to every newly created tenant.
- **20 new pytest tests** (149 total with Milestones 1–7's): deadline creation/completion, recurrence spawning the next occurrence, rejecting completion of an already-completed deadline, the reminder sweep (sends once, never twice), permission enforcement, tenant isolation; and for the portal — invite/accept/login/logout/me, wrong-password and unknown-slug both returning the identical generic error, invite validation (no email, already has access), forgot/reset password (including that reset revokes all sessions), revoke blocking further login, the cross-lead 404 boundary on every resource type, viewing/acting on the caller's own proposals/documents/onboarding/deadlines/appointments, module-gating on every request, staff permission enforcement on portal management, and same-email-different-tenant portal accounts working independently of each other.

### Frontend (`apps/web`)
- `/deadlines` — list, create, and complete deadlines (optionally filtered by `?leadId=`); lead detail page gained a "Deadlines" section.
- `/portal-accounts` — staff list/invite/revoke UI.
- `/portal/{tenantSlug}/login`, `/accept-invitation`, `/forgot-password`, `/reset-password` — the client-facing auth flow, structurally mirroring the staff equivalents but hitting the `/portal/auth/*` endpoints and using the `cops_portal_session` cookie.
- `/portal/{tenantSlug}/dashboard` — the authenticated client home: proposals (accept/decline inline), document requests (inline upload), onboarding checklist progress, upcoming deadlines, and appointments — all scoped automatically to the logged-in client's own lead.
- New `PortalAuthProvider`/`usePortalAuth` (`lib/portal-auth-context.tsx`) — a completely separate auth context from staff's `AuthProvider`, with its own React Query cache key, coexisting cleanly because the underlying cookies never collide.
- Sidebar nav updated with "Deadlines" and "Client Portal" entries.

### Tests & verification
- `ruff check app` — 0 errors. `pytest -q` — 149 passed. `eslint` — 0 errors. `tsc --noEmit` — 0 errors. `next build` — succeeds. `vitest run` — 4 passed.
- Both new Alembic migrations exercised through a full upgrade → downgrade → re-upgrade cycle against real Postgres, against both the dev (`cops`) and test (`cops_test`) databases.
- Manually smoke-tested over real HTTP against a freshly seeded demo tenant (Professional plan) with the API server actually running: invited a lead to the portal, extracted the real invitation email (via a temporary local SMTP listener — see Known limitations), accepted it, logged in at the tenant-slug-scoped URL, confirmed `/portal/auth/me` returned the account; confirmed a cross-lead proposal request returned 404; disabled `client_portal` and confirmed every portal route (including `/me` on an already-authenticated session) returned 403, then re-enabled and confirmed 200 again; confirmed login with an unknown tenant slug and login with a correct email/wrong password both returned the identical `invalid_credentials` response; ran the deadline reminder sweep twice in a row and confirmed the email was sent only on the first run.

## Acceptance criteria — verified

| Criterion (from your Milestone 8 spec) | Verified how |
|---|---|
| Authenticated, self-service client login, distinct from public token links | `PortalAccount`/`PortalSession`, tenant-slug-scoped login, separate `cops_portal_session` cookie coexisting with staff's `cops_session` |
| Clients only ever see their own data | `_assert_belongs_to_lead` boundary on every portal content route, 404 (not 403) on mismatch — verified live |
| Staff control who gets portal access | Explicit invite-only grant model (`portal.manage`), confirmed by design decision and by a test asserting no automatic grant occurs |
| Compliance/service deadline tracking with reminders | `Deadline` model, recurrence support, daily reminder sweep respecting a 7-day lead window, `reminder_sent_at` idempotency |
| Entitlement enforcement, portal-appropriate gating choice | `client_portal` checked on every portal request (not just at invite time) — deliberately stricter than Milestones 6/7's gating, documented and justified in `docs/security/README.md` |
| Reuses existing business logic rather than duplicating it | Portal routes call the same `proposals`/`documents`/`onboarding`/`booking`/`deadlines` service functions staff routes use |

## Known limitations

1. **The sandbox has no real SMTP server** — this was already true for every prior milestone's email-sending code paths, but Milestone 8 is the first time it was directly confirmed to also affect the *staff* invitation flow (not just portal invitations): both call the email provider directly rather than through the soft-failing `send_templated_email` path used by tenant-configurable communications. Worked around for live verification only (a temporary local SMTP listener, removed afterward); not a code change, since intentionally not soft-failing an auth email is correct behavior, not a bug.
2. **New permission codes were unnecessary this milestone** (see above) but the general limitation from every prior milestone still applies to any *future* new permission code: it only applies to newly created tenants, never retroactively backfilled onto existing ones.
3. **No client-initiated password change from within the dashboard** — only the forgot-password flow exists; a "change password while logged in" route was judged out of scope for this milestone and is a natural small follow-up.
4. **No portal account self-deactivation or self-service email change** — both are staff-managed only (`revoke`), by design, since portal identity is tied to the underlying lead record.
5. **Same environment caveats as Milestones 1–7 carry forward**: Docker Compose itself was not run end-to-end in this sandbox; all verification used the same application code run directly against local PostgreSQL 16 + Redis 7, including a real running `uvicorn` instance for the live HTTP smoke test. No browser was available to visually confirm the new UI.

## Pending decisions

None new this milestone — Milestone 1's pending decisions (tenant-URL routing, production email/storage provider choice) remain open and don't block Milestone 9. Milestone 7's malware-scanning production integration question (ClamAV vs. a cloud AV API) also remains open and doesn't block further feature milestones.

## Next action

Awaiting your review of Milestone 8. To proceed, reply exactly: **APPROVE MILESTONE 9**
