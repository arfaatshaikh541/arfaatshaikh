# GRIDKEEP Lead Intelligence — Project Status

## Current milestone
**Milestone 1: Secure SaaS Foundation** — implementation complete, pending your review/approval to proceed to Milestone 2.

## Completed work

### Monorepo & infrastructure
- pnpm workspace (`apps/web`, `packages/ui`, `packages/shared-types`, `packages/config`) and a uv workspace (`apps/api`, `apps/worker`) sharing one Python venv.
- `docker-compose.yml` defining postgres, redis, minio, mailpit, api, worker, web services; `infrastructure/docker/{api,worker,web}/Dockerfile`; `infrastructure/docker/postgres/init/01-init-roles.sh` creating the migrator/app role split inside the container.
- `infrastructure/scripts/setup-local-db.sh` — idempotent local Postgres role/DB setup for running the API directly (used throughout this milestone's own verification, since Docker image pulls are blocked in this build environment — see **Known limitations**).
- Root `.env.example`, `apps/api/.env.example`, `apps/web/.env.example`.

### Backend (`apps/api`, FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL)
- **Core**: config, async DB engine/session, Argon2id password hashing, opaque-token generation/hashing, structured error responses (`AppError` hierarchy → `{error:{code,message,request_id}}`), request-ID + security-header middleware, structlog JSON logging, Redis-backed rate limiting, SMTP mail sending, session/CSRF cookie helpers.
- **Identity**: register, email verification, login (with lockout after repeated failures), logout, password reset (revokes all sessions), `/auth/session`.
- **Tenancy**: tenant creation (seeds default roles/permissions/wallet/trial subscription in one transaction), tenant switching (re-validates membership server-side), invitations (create/accept/expire, plan-limit-aware), tenant status enforcement.
- **Permissions**: table-driven role→permission grants (not hardcoded role checks), 8 default tenant roles + 4 platform roles, composite-FK-enforced separation between tenant and platform roles (a tenant `Membership` structurally cannot reference a platform role; a `PlatformRoleAssignment` structurally cannot reference a tenant role — both backed by DB constraints/triggers, not just application code).
- **Subscriptions/Entitlements**: plan/feature/plan-feature catalog, tenant subscriptions, add-ons, feature overrides, `EntitlementResolver` combining all three, `max_team_members` limit enforced against active memberships **and** pending invitations.
- **Usage/Credit ledger**: wallet with atomic `SELECT...FOR UPDATE`-based reserve/commit/release, append-only transactions, a Celery-driven reservation-expiry sweep.
- **Audit**: tenant-scoped `AuditLog` + platform-scoped `PlatformAuditLog`, written by every state-changing tenancy/support-access action.
- **Platform admin**: tenant listing, time-boxed/reason-logged/revocable support-access grants (dual-write to both platform and tenant audit logs — support access is visible to the tenant it targets, not a silent backdoor).
- **Row Level Security**: enabled + FORCE'd on every tenant-owned table, policy = tenant match OR platform-bypass GUC; `roles`/`role_permissions` additionally allow reading (never writing) `tenant_id IS NULL` platform-scoped rows.
- **Seed data**: idempotent script populating the permission/role/plan catalog and the fictional "Northstar Digital Solutions Demo" tenant with 5 demo users + 1,000 seeded credits.
- **Worker** (`apps/worker`): Celery app + one real scheduled task (`expire_stale_reservations`, every 5 min) proven end-to-end through a live Redis broker and worker process.

### Frontend (`apps/web`, Next.js 16 App Router + React 19 + Tailwind v4)
- Auth pages: login, register, verify-email, forgot-password, reset-password, invitation-accept.
- Onboarding page (create workspace / switch to an existing one).
- Tenant workspace shell (`(tenant)` route group): Dashboard, Team (invite + pending invitations list), Usage & Billing (wallet + credit history), Audit Log — all backed by real API calls, gracefully degrading (a permission-scoped banner, not a crash) when the caller's role lacks the relevant permission.
- `packages/ui`: Button, TextField, Card, Banner — accessible (labelled inputs, `aria-invalid`/`aria-describedby`, focus-visible rings).
- Session-cache invalidation fixed after login/tenant-create/tenant-switch/invitation-accept (see **Known limitations** for how this was found).
- `proxy.ts` (Next 16's renamed middleware convention) for presence-only protected-route redirects.

### Tests
- **Backend**: 25 pytest tests across auth, tenancy/permissions/entitlements, tenant isolation (including a direct RLS-bypass-attempt test against the raw `gridkeep_app` DB role), credit-wallet atomicity, and platform admin/support-access — run against a real, separate PostgreSQL database (`gridkeep_test`) and a real Redis logical DB, with a genuine in-process SMTP server capturing verification/reset/invitation emails (not mocked).
- **Frontend**: `pnpm lint` (ESLint 9 flat config) and `pnpm typecheck` (`tsc --noEmit`, strict mode) both clean.
- **End-to-end**: a 12-step Playwright script (headless Chromium) drove the actual `next dev` server against the actual `uvicorn` API server through register → verify → login → onboarding → create workspace → dashboard → invite teammate → usage page → audit log → logout → protected-route redirect. All 12 checks pass. This is not scripted against mocks — it is the real stack, and it is what surfaced the session-cache bug described below.

## Acceptance criteria (from the approved architecture)

| Criterion | Status |
|---|---|
| Project starts locally | ✅ Backend/worker verified directly; full Docker Compose stack not verified in this build environment (see limitations) |
| Migrations run | ✅ Verified from a clean database, twice |
| Seed data runs | ✅ Verified, and idempotent (re-run produces no duplicates) |
| Registration works | ✅ Backend tests + live Playwright run |
| Login and logout work | ✅ Backend tests + live Playwright run |
| Email verification flow works | ✅ Backend tests + live Playwright run (real SMTP capture) |
| Password-reset flow works | ✅ Backend tests (session revocation verified) |
| Invitations work | ✅ Backend tests + live Playwright run |
| Tenant switching works | ✅ Backend tests |
| Role enforcement works | ✅ Backend tests (permission-denied paths verified, not just happy path) |
| Entitlements work | ✅ Backend tests (`max_team_members` limit blocks the 4th invite) |
| Credit transactions work | ✅ Backend tests + a live Celery/Redis dispatch of the expiry sweep |
| Tenant isolation tests pass | ✅ Including a raw-DB-role RLS bypass attempt |
| Platform roles remain separated | ✅ DB-level composite FK + trigger, not just app code |
| Audit records are created | ✅ Backend tests + live Playwright run |
| Backend tests pass | ✅ 25/25 |
| Frontend lint passes | ✅ |
| Frontend type checking passes | ✅ |
| Production builds pass | ✅ `next build` succeeds; API has no separate "build" step (Python) |

## Architecture decisions
See `docs/adr/0001` through `0007`. Summary: shared-schema+RLS multi-tenancy, server-side sessions, `uv`/`pnpm` tooling with TypeScript pinned to 5.7.3 over the just-released 7.0, campaign-level credit-reservation granularity deferred to Milestone 2, MFA scaffolded only, no billing provider selected yet, and a documented RLS ordering rule + `platform_bypass` escape-hatch pattern discovered and fixed during this milestone.

## Known limitations

1. **Docker Compose stack not verified end-to-end in this build environment.** This session's outbound network egress policy blocks Docker Hub image pulls (`production.cloudfront.docker.com` returns a 403 policy denial), so `docker compose up` could not be run here. All verification instead ran the same services natively: PostgreSQL 16 and Redis were already installed in this sandbox and used directly; the FastAPI app, Celery worker, and Next.js dev server were run directly via `uv run` / `pnpm dev`. The `docker-compose.yml` and Dockerfiles are believed correct (they mirror the exact configuration verified natively) but **you should run `docker compose up` yourself before relying on it** — that is the one meaningful gap between "verified" and "should work."
2. **MFA is scaffolded, not enrollable** (ADR-0005) — by design, per your approval.
3. **No billing provider integration** (ADR-0006) — by design, per your approval; plans/credits are seed data today.
4. **RLS discipline is manual today.** The ordering rule in ADR-0007 (`set_tenant_context` before any RLS-protected query) is not enforced by a linter or CI check — a future service function could reintroduce the same class of bug if the rule isn't followed. A CI check for "every new tenant-owned table has a matching RLS migration" and a code-review checklist item for the ordering rule are recommended before Milestone 10's security audit, but are not built yet.
5. **No CI/CD pipeline yet.** GitHub Actions workflows (lint/test/build/scan on push) are not part of Milestone 1's approved scope and have not been created.
6. **Object storage (MinIO) is configured but unexercised.** Milestone 1 has no file-storage feature (exports are Milestone 7), so the S3 client configuration exists in `core/config.py` but was never actually connected to in this milestone's verification.
7. **Frontend uses hand-written types** (`apps/web/lib/types.ts`), not OpenAPI-generated ones — reasonable at this API-surface size; `packages/shared-types` is reserved for generated types later (see its README).

## Unresolved risks

- **Connection-pool GUC leakage class of bug** (ADR-0007): fixed everywhere it was found by manual audit during this milestone, but the codebase has no automated guard against a *future* service function making the same mistake. Recommend a lightweight integration test pattern (assert a fresh session with no context set returns zero rows for every RLS table) be added as a standing regression test in an early Milestone 2 task, not deferred indefinitely.
- **Single shared Postgres instance**: no read replica, no connection-pool sizing exercise under load. Fine at Milestone 1 scale; a real concern once Milestone 2's campaign engine adds background write load.
- **Rate limiting is IP/account-keyed only**, no distributed abuse detection. Adequate for now.

## Pending approvals
None outstanding from the original architecture response — all 8 items listed under "architecture decisions requiring approval" were approved when you sent `APPROVE MILESTONE 1`. ADR-0007 documents a decision made *during* implementation (the RLS ordering fix) that didn't exist at architecture-review time; it doesn't require separate approval since it's a bug fix to already-approved behavior (tenant isolation must work correctly), but it's called out here for transparency per rule #15 (explain major architecture decisions before/as they're made).

## Next action
Awaiting your review of Milestone 1. When ready, send `APPROVE MILESTONE 2` to begin the Campaign and Job Engine milestone (campaigns, filters, search areas, source selection, estimates, credit reservations wired to real campaign creation, state machine, background task processing, progress tracking, pause/cancel, retries, idempotency, per-tenant concurrency limits, mock connector).

---

## Complete file inventory (created or modified in Milestone 1)

### Root
`package.json`, `pnpm-workspace.yaml`, `pyproject.toml`, `.gitignore`, `.env.example`, `docker-compose.yml`

### Infrastructure
`infrastructure/docker/postgres/init/01-init-roles.sh`, `infrastructure/docker/api/Dockerfile`, `infrastructure/docker/worker/Dockerfile`, `infrastructure/docker/web/Dockerfile`, `infrastructure/scripts/setup-local-db.sh`

### Backend — `apps/api`
`pyproject.toml`, `.env.example`, `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/5be9811cd917_*.py`, `alembic/versions/8a1f2c3d4e5f_*.py`, `alembic/versions/fe3f382fcffa_*.py`,
`app/main.py`, `app/dependencies.py`,
`app/core/{config,db,security,exceptions,middleware,rate_limit,logging,mail,cookies,model_registry}.py`,
`app/modules/identity/{models,schemas,repositories,services,routes}.py`,
`app/modules/tenancy/{models,schemas,repositories,services,routes}.py`,
`app/modules/permissions/{models,catalog,repositories}.py`,
`app/modules/subscriptions/{models,schemas,repositories,routes}.py`,
`app/modules/entitlements/service.py`,
`app/modules/usage/{models,schemas,repositories,services,routes}.py`,
`app/modules/audit/{models,schemas,service,routes}.py`,
`app/modules/platform_admin/{models,schemas,repositories,services,routes}.py`,
`app/seed/seed_data.py`,
`tests/{conftest,helpers,test_auth,test_tenancy_and_permissions,test_tenant_isolation,test_credit_wallet,test_platform_admin}.py`

### Worker — `apps/worker`
`pyproject.toml`, `worker/{celery_app,queues,beat_schedule,tasks}.py`

### Frontend — `apps/web`
`package.json`, `tsconfig.json`, `next.config.ts`, `postcss.config.mjs`, `eslint.config.mjs`, `.env.example`, `.env.local`, `proxy.ts`,
`app/layout.tsx`, `app/page.tsx`, `app/providers.tsx`, `app/globals.css`,
`app/(auth)/login/page.tsx`, `app/(auth)/register/page.tsx`, `app/(auth)/verify-email/page.tsx`, `app/(auth)/forgot-password/page.tsx`, `app/(auth)/reset-password/page.tsx`, `app/(auth)/invitations/accept/page.tsx`,
`app/onboarding/page.tsx`,
`app/(tenant)/layout.tsx`, `app/(tenant)/_components/TenantShell.tsx`, `app/(tenant)/dashboard/page.tsx`, `app/(tenant)/team/page.tsx`, `app/(tenant)/usage/page.tsx`, `app/(tenant)/audit/page.tsx`,
`lib/{api,types,session}.ts`

### Shared packages
`packages/ui/package.json`, `packages/ui/src/{Button,TextField,Card,Banner,index}.tsx|ts`,
`packages/shared-types/README.md`, `packages/config/README.md`

### Docs
`docs/project-status.md`, `docs/adr/0001` through `0007`
