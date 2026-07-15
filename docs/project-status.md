# GRIDKEEP Cyber OS — Project Status

Last updated: 2026-07-15 (Milestone 1 implementation)

## Current Milestone

**Milestone 1: Secure SaaS Core** — implementation complete, pending your review and explicit approval to proceed to Milestone 2.

## Completed Work

### Monorepo & tooling
- pnpm workspace (`apps/*`, `packages/*`), shared TypeScript/Tailwind config (`packages/config`)
- `packages/security-contracts` — single source of truth for permission keys, role names, module keys,
  tenant statuses and automation modes, mirrored in Python (`apps/api/core/security_contracts.py`) and
  kept in sync by an automated test (`tests/test_security_contracts_sync.py`)
- `packages/ui` — dark-neutral, orange-accent component library (Button, TextInput, Card, Badge, Alert)
  matching the approved design system
- `packages/connector-sdk`, `packages/shared-types` — scaffolded placeholders, explicitly labelled
  out-of-scope for Milestone 1 (Milestone 2 and later)

### Backend (`apps/api`, FastAPI + SQLAlchemy 2 async + PostgreSQL)
- **core**: settings (Pydantic Settings), Argon2id password hashing, opaque session/reset/invitation
  tokens (hashed at rest), structured error model with safe production error responses, security
  headers + CORS middleware, in-process rate limiter (documented as needing a Redis-backed limiter for
  multi-instance production deployments), the full 9-step authorization dependency pipeline
  (`core/deps.py`)
- **tenancy**: Tenant, TenantSettings, TenantSecurityProfile, TenantDomain; self-service onboarding
  (creates tenant + Tenant Owner atomically in one transaction)
- **identity**: User, Session, PasswordResetToken, EmailVerificationToken; login/logout, email
  verification, password reset (invalidates all sessions), tenant switching (server-revalidated)
- **permissions**: Role, Permission, RolePermission, Membership, Invitation; default tenant roles
  (Tenant Owner, Security Administrator, Security Analyst, IT Administrator, Compliance Manager,
  Incident Responder, Executive Viewer, Read-Only Auditor) and platform roles (Platform Super Admin,
  Platform Security Operator, Platform Support Engineer, Platform Auditor) seeded from
  `security_contracts.py`, structurally separate from tenant roles
- **subscriptions / entitlements**: Module, Feature, SubscriptionPlan, PlanFeature, TenantSubscription,
  AddOn, TenantAddOn, TrialGrant, TenantFeatureOverride, UsageMetric, UsageRecord, FeatureLimit;
  `resolve_entitlements()` merges plan → add-ons → trial grants → tenant overrides (grant/revoke),
  computed fresh per request, never cached client-side
- **credential_vault**: `IntegrationCredential` model + `VaultAdapter` interface with a labelled
  **LOCAL** envelope-encryption adapter (AES-256-GCM data key, HKDF-derived, wrapped key-encryption
  key from `VAULT_LOCAL_MASTER_KEY`); store/rotate/revoke/list; the raw secret is never returned by any
  API response
- **platform_admin**: SupportAccessGrant — time-boxed, audited, tenant-visible; no impersonation;
  Milestone 1 grants activate immediately for the requesting platform user rather than requiring a
  second approver (see Known Limitations)
- **audit**: append-only `audit_logs`, enforced at the database level (no UPDATE/DELETE RLS policy
  under `FORCE ROW LEVEL SECURITY`, verified by test)
- **Alembic migrations**: baseline schema (29 tables) + a dedicated RLS-policy migration (16 policies
  across 12 tables, plus 3 helper SQL functions)
- **Seed scripts**: `seed/bootstrap.py` (idempotent platform catalogue — permissions, roles, modules,
  features, the `trial` plan; safe for every environment) and `seed/demo.py` (fictional
  **GRIDKEEP Platform Demo** platform admin + **Northstar Advisory Demo** tenant with 5 fictional
  users, one per default tenant role; refuses to run when `ENVIRONMENT=production`)

### Worker (`apps/worker`, Celery + Redis)
- `cleanup_expired_sessions`, `expire_support_access_grants` (real, scheduled, tenant-RLS-aware —
  iterates tenants rather than using a cross-tenant bypass), `health_check`
- Celery Beat schedule; queue naming matches the architecture doc (`sync`/`ingest`/`correlate`/
  `actions`/`reports`/`default`) even though only `default` has real work in Milestone 1
- Reuses `apps/api`'s `core`/`db`/`modules` packages via a `sys.path` insert — documented as a
  Milestone 1 simplification (see Known Limitations)

### Frontend (`apps/web`, Next.js 14 App Router)
- Auth screens: login, onboarding (self-service tenant creation), forgot/reset password, verify email,
  accept invitation, select-workspace (multi-tenant login)
- Protected tenant shell: sidebar nav, tenant/role indicator, sign-out; redirects unauthenticated users
  to `/login` and users without a selected workspace to `/select-workspace`
- Dashboard (workspace status, subscription, entitled modules — real data from the API) and
  Settings → Users (list + invite, permission-gated) and Settings → Subscription
- `AuthProvider` (TanStack Query-backed `/api/auth/me`) drives permission-aware rendering; the backend
  re-checks every permission regardless of what the UI shows
- CSRF double-submit implemented end-to-end (cookie + `X-CSRF-Token` header on every mutating request)

### Infrastructure
- `docker-compose.yml`: postgres, redis, minio (object storage), mailhog (mail capture), api, worker,
  beat, web — validated with `docker compose config` (see Known Limitations: not run end-to-end)
- Dockerfiles for api, worker (shares the api dependency install), web (multi-stage pnpm build)
- `infrastructure/scripts/`: `wait-for.sh`, `migrate.sh`, `seed.sh`, `bootstrap.sh`
- `.github/workflows/ci.yml`: backend (ruff + pytest against real Postgres/Redis service containers),
  frontend (eslint + tsc + vitest + `next build`), security-contracts sync check

## Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| Project starts locally | ✅ (non-Docker) / ⚠️ (Docker) | API, worker, and web all verified running directly against local Postgres/Redis; `docker compose config` validates syntax but `docker compose up` was never executed (no Docker daemon in this sandbox) — see Known Limitations |
| Migrations run | ✅ | `alembic upgrade head` run repeatedly against a real Postgres 16 instance; both migrations (baseline schema + RLS policies) apply and roll back cleanly |
| Seed data runs | ✅ | `seed/bootstrap.py` and `seed/demo.py` run and are idempotent (verified by running twice) |
| Login and logout work | ✅ | Verified via automated tests and a real browser session (Playwright) against the live API and Next.js dev server |
| Invitations work | ✅ | `test_invitation_accept_flow`, `test_executive_viewer_cannot_manage_users`; also exercised live in the browser (invite form → "Invitation sent.") |
| Password reset architecture works | ✅ | `test_password_reset_flow` — old password rejected after reset, new password accepted, all sessions revoked |
| Tenant switching works | ✅ | `test_cannot_switch_to_another_tenants_membership` (negative case) + login-response `active_membership_id` auto-select (positive case) |
| Role enforcement works | ✅ | `test_rbac.py` — Executive Viewer denied `users.manage`; Tenant Owner has full tenant permissions |
| Entitlements work | ✅ | `test_entitlements.py` — 6 tests covering plan grants, expired subscriptions, tenant overrides (grant/revoke/expiry), module-from-feature derivation |
| Tenant isolation passes | ✅ | `tests/security/test_tenant_isolation.py` — 6 tests: cross-tenant credential access, cross-tenant tenant-switch, member-list scoping, client-supplied `tenant_id` injection, raw RLS behaviour with no session context, RLS-rejected cross-tenant INSERT |
| Credential encryption works | ✅ | `test_credential_vault.py` — envelope-encryption round-trip, tampering detection, per-call ciphertext uniqueness, store/rotate/revoke against a real Postgres row, manually verified plaintext-never-in-DB via direct query |
| Platform roles remain separated | ✅ | `test_platform_admin.py`; `TenantContext`/`PlatformContext` are structurally distinct types with no shared permission evaluation path |
| Audit records are created | ✅ | `test_audit.py` — login creates a record; UPDATE/DELETE against `audit_logs` verified to have zero effect (RLS-enforced append-only) |
| Backend tests pass | ✅ | **47/47** passing (`pytest -q`, run repeatedly, not flaky across multiple full-suite runs) |
| Frontend lint passes | ✅ | `pnpm exec eslint .` — 0 errors |
| Frontend type checking passes | ✅ | `pnpm exec tsc --noEmit` — 0 errors |
| Production builds pass | ✅ | `next build` — all 14 routes compile and prerender; backend imports cleanly, `uvicorn main:app` boots and serves `/healthz`/`/readyz` |

## Test Results (as actually executed in this session)

```
apps/api: pytest -q          → 47 passed
apps/api: ruff check .       → All checks passed
apps/web: pnpm exec eslint . → 0 errors
apps/web: pnpm exec tsc --noEmit → 0 errors
apps/web: pnpm exec vitest run   → 10 passed (3 files)
apps/web: next build         → succeeded, 14/14 routes
```

All of the above were executed directly in this session — none are claimed without having been run.
Manual, real end-to-end verification also performed: `curl`-driven auth/tenant/RBAC/credential-vault
flows against a live `uvicorn` process, and a real headless-Chromium (Playwright) session driving the
Next.js dev server through login → dashboard → Users → invite, screenshotted for visual confirmation of
the dark/orange design system.

**Not executed**: `docker compose up` (no Docker daemon available in this sandbox — Dockerfiles and
compose file are written and `docker compose config` confirms valid syntax, but the images have never
actually been built or run). This should be the first thing verified in a real Docker-capable
environment before treating the containerized path as production-ready.

## Architecture Decisions (made or refined during implementation)

Beyond the 10 ADRs approved before implementation began, two additional decisions were made while
building, both documented inline where they matter:

- **RLS session-variable NULL handling**: `current_setting(name, true)` on a custom GUC returns the
  empty string (not SQL `NULL`) once that GUC has ever been set on a given Postgres backend/connection,
  even after the setting transaction ends. A bare `::uuid`/`::boolean` cast on `''` raises rather than
  evaluating to NULL. Fixed with three helper SQL functions (`app_current_tenant_id()`,
  `app_current_user_id()`, `app_is_platform_admin()`) that wrap every `current_setting()` call in
  `nullif(..., '')` before casting. This is now the only way any RLS policy reads session context —
  see `migrations/versions/762368bc730d_row_level_security_policies.py`.
- **Background jobs and RLS**: a scheduled sweep needing to touch rows across *all* tenants (expiring
  support-access grants) cannot issue one unscoped query against an RLS-protected table — the policy
  has no platform-wide bypass, by design (Rule 19). `worker/tasks.py` instead lists tenant ids from the
  (non-RLS) `tenants` table and iterates, setting tenant context per iteration. This is the pattern any
  future cross-tenant background job should follow.

## Known Limitations

- **Docker Compose never executed end-to-end** — no Docker daemon in this development sandbox. Syntax
  validated (`docker compose config`); the built images themselves are unverified. Verify this first in
  a Docker-capable environment.
- **Support-access grants activate immediately** for the requesting platform user (who already holds
  `platform.support_access`) rather than requiring a second approver. Still fully time-boxed, audited,
  revocable, and tenant-visible. A second-approver workflow is a reasonable Milestone 2/17 hardening
  item, not a Milestone 1 blocker.
- **Rate limiting is in-process** (`core/middleware.py`'s `InMemorySlidingWindowLimiter`), correct for a
  single API instance but will not coordinate across multiple instances in a horizontally-scaled
  deployment. The swap point to a Redis-backed limiter is isolated and documented in the code.
- **MFA is schema-only** — `User.mfa_totp_secret_encrypted` / `mfa_enabled` and `Session.mfa_verified` /
  `step_up_expires_at` exist and `core/deps.require_step_up` is implemented and unit-testable, but no
  route enforces MFA setup or challenge yet (no Milestone 1 route requires step-up). Full MFA
  enrollment/challenge UX is appropriately Milestone-1-adjacent but not yet built.
- **Worker/API code-sharing via `sys.path`, not a packaged library.** `apps/worker` imports
  `apps/api`'s `core`/`db`/`modules` directly. Fine for Milestone 1's two maintenance tasks; extracting
  shared domain code into an installable package (e.g. `packages/gridkeep-core`) before Milestone 2
  adds real connector-sync/action-execution worker code is recommended, not required.
- **Single database role for both migrations and the API runtime** (`gridkeep`) in the local/dev
  configuration, rather than the least-privilege split described in the architecture doc (§7). Both
  roles being genuinely different (migration role with DDL rights, runtime role restricted to
  DML+RLS) is a production-hardening item for Milestone 17, not required for Milestone 1's local
  correctness.
- **Object storage, evidence integrity, and email delivery are not yet real.** `MinIO` and `Mailhog`
  are wired into `docker-compose.yml` but no code path uses them yet — invitation/verification/reset
  emails are dispatched via a clearly-labelled `email_dispatch_simulated` structured-log line (dev-only,
  never a real send), and there is no evidence-object storage code yet (that's Milestone 2+ scope: the
  Milestone 1 acceptance criteria only requires the *object storage service* to be present in the
  Compose stack, not consumed).
- **`packages/connector-sdk` and `packages/shared-types` are empty placeholders**, explicitly labelled
  as out of scope until Milestone 2, per Rule 9 (label simulator/adapter/placeholder code clearly).

## Unresolved Risks

- The in-memory rate limiter and the lack of a second-approver support-access flow are both real,
  if modest, security posture gaps versus the target architecture — flagged above, not hidden.
- No dependency/container/secret scanning has run yet (CI workflow does not yet include these) —
  planned for Milestone 17 (Production Hardening) per the approved milestone plan, but noting it here
  so it isn't forgotten before a real production deployment.
- The `docker-compose.yml` web service builds the whole monorepo context; this hasn't been checked for
  build-time or image-size sanity since it was never actually built.

## Pending Approvals

- This Milestone 1 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps are documented rather than hidden.
- Recommend explicit review of the two mid-implementation architecture decisions (RLS NULL-handling
  helper functions, background-job tenant iteration pattern) since they weren't part of the originally
  approved architecture document, even though they follow directly from its principles.

## Next Action

Awaiting your review. Once you're satisfied, send **`APPROVE MILESTONE 2`** to begin the Integration SDK
and Asset Graph milestone (connector catalogue, connector SDK, mock connectors, encrypted credential
integration onboarding, integration health, sync jobs, asset inventory/identifiers/relationships/
ownership/criticality, asset graph, change tracking).
