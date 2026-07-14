# Project status

**Current milestone:** Milestone 1 — Core SaaS Foundation
**Status:** Complete, verified against a real PostgreSQL + Redis stack. Awaiting your review before starting Milestone 2.
**Last updated:** 2026-07-14

---

## What was built

### Monorepo & infrastructure
- `apps/api` (FastAPI, modular monolith), `apps/worker` (Celery), `apps/web` (Next.js App Router).
- `infrastructure/docker/docker-compose.yml`: postgres, redis, minio, mailhog, api, worker, web.
- `infrastructure/docker/postgres/init-roles.sh`: provisions `app_migrator` (BYPASSRLS, owns schema) and `app_runtime` (NOBYPASSRLS, used at request time) roles — the same script runs in local dev and is documented for production.
- `.env.example` with every variable documented, `REQUIRES EXTERNAL CREDENTIAL` flagged where relevant.
- `.github/workflows/ci.yml`: backend (ruff, alembic migrate, pytest against real ephemeral Postgres+Redis) and frontend (eslint, tsc, vitest, next build) jobs.

### Backend (`apps/api`)
- **Core**: Pydantic Settings config, SQLAlchemy engine/session with RLS session-variable helpers, Argon2id + opaque-token session helpers, structured JSON logging, global exception handling (no stack traces to clients), rate limiting, pagination.
- **Tenancy module**: `Tenant`, `TenantSettings`, `TenantDomain`; status lifecycle (active/suspended/read_only/archived).
- **Identity module**: `User`, `Membership`, `Invitation`, `Session`, email-verification and password-reset tokens, login-attempt log. Full auth flows: login, logout, invitation-based registration, forgot/reset password, email verification, tenant switching.
- **Permissions module**: `Role`, `Permission`, `RolePermission`; full tenant permission catalog + disjoint platform permission catalog; default tenant roles (Tenant Owner, Administrator, Manager, Sales Agent, Support Agent, Viewer) provisioned per-tenant from templates.
- **Subscriptions module**: `Module`, `Feature`, `SubscriptionPlan`, `PlanFeature`, `TenantSubscription`, `AddOn`, `TenantAddOn`. Seed catalog covers all 17 spec'd modules plus an `account` module for seat limits, and the four spec'd plans (Starter/Growth/Professional/Enterprise).
- **Entitlements module**: `TenantFeatureOverride`, `UsageMetric`, `UsageRecord`; the `resolve_entitlements()` function is the single source of truth consumed by both backend enforcement (`require_module`/`require_feature`/`check_usage_limit`) and the `/me/entitlements` endpoint the frontend polls. Usage-limit checks use `SELECT ... FOR UPDATE` for concurrency safety.
- **Audit module**: `AuditLog` (immutable, insert-only), `SupportAccessLog`, `FeatureChangeLog`; every auth/tenancy/role/subscription/entitlement mutation writes an entry.
- **Platform admin module**: tenant creation (with owner provisioning), status changes, plan assignment, add-on grants, feature overrides, usage view, audit/support-access log views — all behind `require_platform_admin`.
- **Database**: 2 Alembic migrations (schema, then RLS policies) — both applied, downgraded, and re-applied cleanly against a real PostgreSQL 16 instance during this session. Row-level security enabled and `FORCE`d on every tenant-owned table.
- **Seed script** (`app/db/seed/run.py`): idempotent; platform admin, demo tenant "Rafana Advisory Demo" (Growth plan) with 3 demo users, full permission/module/plan/add-on catalog.
- **Worker**: Celery + beat, three scheduled cleanup tasks (expired sessions, expired invitations, expired feature overrides), all re-using the API package's service layer directly.

### Frontend (`apps/web`)
- Next.js 15 App Router, TypeScript strict mode, Tailwind (dark neutral UI, restrained orange accent per the approved design direction).
- Auth pages: login, accept-invitation, forgot-password, reset-password, verify-email.
- Tenant app: dashboard shell, sidebar with tenant switcher and permission-gated nav, settings, users (list + invite), roles (list + create custom role), subscription/module-access view.
- Platform admin app: overview, tenant list + create, tenant detail (status/plan/overrides/usage), plans, modules, audit logs.
- `useEntitlements()` / `RequireModule` / `RequirePermission` — frontend hints only; every route independently re-checks on the backend.
- TanStack Query for all data fetching; React Hook Form + Zod for validation.

### Tests
- **Backend**: 40 pytest tests, all running against a real PostgreSQL test database (RLS enabled) and real Redis — no mocked DB. Savepoint-per-test isolation. Covers: login/logout/throttling/password-reset/email-verification, invitation accept flow, tenant isolation (cross-tenant reads, tenant-switch rejection, per-tenant data separation), tenant-status enforcement (suspended/read-only/archived, restore without data loss), authorization (permission checks, platform-permission-not-assignable, system-role-immutable, cross-role rejection), entitlements (module/feature gating, plan upgrade/downgrade preserving data, feature overrides, add-on grants, usage-limit enforcement including the exact-boundary case), and platform admin (tenant CRUD, status/plan changes, platform/tenant role separation).
- **Frontend**: 4 vitest tests (Button component, login form validation) using Testing Library.
- `ruff check app` — 0 errors. `eslint` — 0 errors. `tsc --noEmit` — 0 errors. `next build` — succeeds, 18 routes.

## Acceptance criteria — verified

| Criterion | Verified how |
|---|---|
| Project starts locally | `apps/api`, `apps/worker` run against real Postgres 16 + Redis 7 in this session (docker-compose is written and `docker compose config` validated, but the actual container build/run was not exercised — see Known Limitations) |
| Migrations run | `alembic upgrade head` / `downgrade -1` / re-`upgrade head` all exercised against real Postgres |
| Seed data runs | `python -m app.db.seed.run`, twice (idempotency confirmed) |
| Login works | Automated test + manual curl smoke test against seeded demo user |
| Logout works | Automated test: session cookie no longer authenticates after logout |
| Password reset architecture works | Automated test: request → email (captured) → reset → old password fails, new password works → old session revoked |
| Tenant switching works | Automated test + manual smoke test; rejects switching into a non-member tenant |
| Role checks work | Automated tests: Viewer blocked from `/tenant/users`, permission catalog never exposes platform permissions |
| Two tenants coexist, isolated | Automated tests: separate membership lists, settings updates don't leak, cross-tenant switch rejected |
| Module entitlements enforced by backend | Automated test asserts `assert_module_enabled` raises for a module not in the Starter plan; manual smoke test confirmed the full HTTP path (Starter plan tenant's `/me/entitlements` omits `booking`) |
| Disabled module API access rejected | Same mechanism as above — `require_module()` is the actual dependency every future module route will use |
| Frontend reflects entitlements | `useEntitlements()` drives nav visibility; manually verified against the running API during this session (not screenshotted, no browser available in this sandbox — see Known Limitations) |
| Subscription plan assignment works | Automated test + manual smoke test (starter → professional, unlocks `document_collection`) |
| Add-on / override access works | Automated tests + manual smoke test (WhatsApp add-on unlocks `whatsapp` module on a Starter-plan tenant) |
| Suspended tenant restrictions work | Automated test + manual smoke test (403 on all access; GET allowed, PATCH blocked in read-only; full access restored with zero data loss) |
| Platform roles stay separate | Automated test: tenant Administrator gets 403 on every `/platform/*` route |
| Backend tests pass | `pytest -q` → 40 passed |
| Frontend lint passes | `eslint .` → 0 errors |
| Frontend type checking passes | `tsc --noEmit` → 0 errors |
| Production builds pass | `next build` → succeeds |

## Known limitations

1. **Docker Compose was not actually run end-to-end in this session.** The dev sandbox has no Docker daemon. Every backend/worker code path was instead verified by running the same Python processes directly against a locally-installed PostgreSQL 16 and Redis 7 (identical role provisioning, identical migrations, identical RLS policies) — this exercises the same application code, but the Dockerfiles/compose networking themselves are unverified. **Recommend running `docker compose up --build` once in an environment with Docker before considering this production-ready.**
2. **No browser was available to visually verify the frontend.** Lint, typecheck, unit tests, and production build all pass, and the API endpoints they call were manually confirmed working — but no screenshot or interactive browser session confirms the UI renders/behaves correctly. **Recommend a manual click-through before Milestone 2.**
3. **Session lookups are DB-only, not Redis-cached**, per the architecture doc's noted trade-off (correctness over premature optimization) — revisit if login-path latency becomes a real issue.
4. **Communications module is a minimal SMTP-only stub** (`app/core/email.py`) — plain text/HTML, no DB-driven templates. Full templating is Milestone 3 scope per your spec.
5. **CSRF double-submit token is not implemented** — `SameSite=Lax` cookies are the interim mitigation. Flagged for Milestone 10.
6. **Rate limiting is login-only**, not platform-wide. Flagged for Milestone 10.
7. **`packages/ui`, `packages/shared-types`, `packages/config`** from the original architecture sketch were **not created** — nothing in Milestone 1 needed cross-app sharing yet (only one frontend app exists). They'll be introduced when a real second consumer appears.
8. Two bugs were found and fixed *during this session's own testing* (not present in the final code, but worth recording): an initial RLS policy design didn't account for the "list my own tenants before selecting one" login/switch-tenant read path (fixed via an `app.current_user_id` GUC and membership-based visibility policies on `tenants`/`roles`), and `audit_logs` initially blocked inserts from public, pre-authentication endpoints (fixed via an insert-unrestricted policy, since audit `tenant_id` is always server-assigned, never client input).
9. `npm audit` still reports 2 moderate advisories from Next.js's own bundled internal `postcss` dependency (not our top-level one, which is patched) — this is an upstream Next.js packaging choice, not something fixable from this repo without downgrading Next.js.

## Pending decisions

From the architecture document's open items — proceeded with the stated recommendations since no response was given; flagging here in case you want to change any before Milestone 2:
1. **Tenant identification in URLs**: implemented as derived from session only (no subdomain/path-slug routing yet) — the Next.js app doesn't route by tenant slug in the URL at all in M1. Confirm this is fine for now, or if you want `/t/{slug}/...`-style URLs before Milestone 2.
2. **Read-only vs suspended semantics**: implemented as recommended — `suspended` blocks everything, `read_only` allows GET/HEAD/OPTIONS only.
3. **Session lifetime**: 12h absolute / 60min idle, as recommended, configurable via env vars.
4. **Production email/storage providers**: not chosen — `.env.example` documents the adapter points (SMTP host for email, S3-compatible endpoint for storage) but no specific provider is wired up. Needed before a real deployment, not before Milestone 2.

## Next action

Awaiting your review of Milestone 1. To proceed, reply exactly: **APPROVE MILESTONE 2**

Milestone 2 (per the approved architecture) is Lead Capture and CRM:
services, qualification forms, custom fields, public enquiry form, lead
creation, duplicate detection, lead table, Kanban pipeline, lead detail,
notes, tags, tasks, attachments, activity timeline, filters, search, and
entitlement enforcement on all of it.
