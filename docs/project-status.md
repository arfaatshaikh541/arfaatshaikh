# GRIDKEEP Cyber OS — Project Status

Last updated: 2026-07-15 (Milestone 3 implementation)

## Current Milestone

**Milestone 3: Findings and Risk Engine** — implementation complete, pending your review and explicit
approval to proceed to Milestone 4. Milestones 1 (Secure SaaS Core) and 2 (Integration SDK and Asset
Graph) are complete and merged; their sections below are preserved as-is.

## Milestone 1 — Completed Work

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

## Milestone 1 — Acceptance Criteria

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

## Milestone 1 — Test Results (as actually executed in that session)

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

## Milestone 1 — Architecture Decisions (made or refined during implementation)

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

## Milestone 1 — Known Limitations

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

## Milestone 1 — Unresolved Risks

- The in-memory rate limiter and the lack of a second-approver support-access flow are both real,
  if modest, security posture gaps versus the target architecture — flagged above, not hidden.
- No dependency/container/secret scanning has run yet (CI workflow does not yet include these) —
  planned for Milestone 17 (Production Hardening) per the approved milestone plan, but noting it here
  so it isn't forgotten before a real production deployment.
- The `docker-compose.yml` web service builds the whole monorepo context; this hasn't been checked for
  build-time or image-size sanity since it was never actually built.

---

## Milestone 2 — Completed Work

### Connector SDK (`packages/connector-sdk`, new installable Python package)
- Provider-neutral contract: `ConnectorDefinition`, `NormalizedRecord`, `RelationshipRecord`,
  `HealthCheckResult`, `ActionSpec`, and an abstract `Connector` base class (`authenticate()` /
  `health_check()` / `sync()` / `disconnect()`) — the same shape any future real provider adapter
  (identity, EDR, cloud, backup, threat intel) will implement
- Five mock connectors (`mocks/identity.py`, `endpoint.py`, `cloud.py`, `backup.py`, `threat_intel.py`),
  each explicitly `is_simulator=True` and returning deterministic fake data — per Rule 9, simulators are
  labelled everywhere (catalogue entries, API responses, UI badges) and are excluded from the catalogue
  in production (`settings.is_production`)
- `registry.py` maps `provider_id` → connector class; `testing/contract.py` runs a shared contract-check
  suite (`run_connector_contract_checks`) against any connector, mock or real
- 12 passing tests (`packages/connector-sdk/tests/test_mock_connectors_contract.py`)

### Backend — `modules/integrations` (catalog, connect/disconnect, health, sync runs)
- Models: `IntegrationCatalogEntry`, `TenantIntegration`, `IntegrationHealth`, `IntegrationSyncRun`
- `connect_integration()`: validates the catalog entry, instantiates the connector, calls
  `authenticate()`, stores the credential via the Milestone 1 vault (`credential_vault`), records an
  initial health check, all in one flow — a bad credential fails before anything is persisted
- `disconnect_integration()`: revokes the vault credential, marks the integration `disconnected`
- Routes: `GET /api/integrations/catalog`, `GET|POST /api/integrations`,
  `POST /api/integrations/{id}/disconnect`, `GET /api/integrations/{id}/health`,
  `GET /api/integrations/{id}/sync-runs`, `POST /api/integrations/{id}/sync` (enqueues a Celery task and
  returns immediately with a `sync_run_id` + `task_id`)
- All mutating routes are CSRF-protected, permission-gated (`integrations.view` / `integrations.manage`),
  and audited (`integrations.connected` / `.disconnected` / `.sync_triggered`)

### Backend — `modules/assets` (asset graph)
- Models: `AssetType`, `Asset`, `AssetIdentifier`, `AssetRelationship`, `AssetOwner`, `AssetTag`,
  `AssetChange`
- `ingestion.py`: two-pass, idempotent ingestion of a connector's `NormalizedRecord`/`RelationshipRecord`
  stream — pass 1 upserts assets (deduplicated on `(tenant_id, identifier_type, identifier_value)`,
  attribute diffs written to append-only `AssetChange` rows), pass 2 resolves relationships, so
  relationship records can reference assets regardless of yield order within a sync
  `AssetChange` is append-only at the database level (no UPDATE/DELETE RLS policy — the same pattern
  Milestone 1 used for `audit_logs`)
- Routes: `GET /api/assets` (filterable by type/criticality/search), `GET /api/assets/{id}` (identifiers,
  relationships in both directions, owners, tags), `GET /api/assets/{id}/changes`,
  `PATCH /api/assets/{id}/criticality`, `POST /api/assets/{id}/owners`
- 16 passing tests across `test_integrations_and_assets.py` and `test_asset_ingestion.py`, covering
  catalogue visibility, connect/disconnect, dedup on re-sync, relationship resolution, cross-tenant
  isolation, and criticality/ownership updates

### Worker (`apps/worker`) — real sync task
- `run_integration_sync(tenant_id, tenant_integration_id, sync_run_id)`: loads the tenant integration,
  decrypts its vault credential, runs the connector's `sync()`, ingests the resulting records via
  `modules.assets.ingestion`, updates the sync run and a fresh health check — atomic per task, failure
  path records `sync_run.status="failed"` with the error message and an `IntegrationHealth` row
  (`status="error"`) rather than leaving the run in `running` forever
- Worker now consumes `default,sync,ingest,correlate,actions,reports` (previously only `default` had
  real work) — requires the explicit `-Q` flag at startup (Celery does not consume declared-but-unused
  queues by default), updated in the Dockerfile CMD and README

### Frontend (`apps/web`)
- `/integrations`: catalogue grid (provider name, category, simulator badge, supported data types),
  inline connect form (label + credential) per catalogue entry, and a connected-integrations table
  linking to detail pages
- `/integrations/[id]`: status, "Sync now" / "Disconnect" actions (permission-gated on
  `integrations.manage`), sync-run history (auto-refreshes every 5s while on the page), health-check
  history
- `/assets`: filterable inventory table (search, asset type, criticality)
- `/assets/[id]`: overview (exposure, confidence, last observed/assessed), identifiers, relationships
  (linked to the related asset's own detail page), owners (with an owner-assignment control gated on
  `assets.manage` **and** `users.manage`, since `it_administrator` has the former but not the latter),
  tags, and change history
- Nav updated with Integrations and Assets links; active-state highlighting extended to match nested
  detail routes (`/integrations/[id]`, `/assets/[id]`)

## Milestone 2 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| Connector SDK with a stable contract | ✅ | `packages/connector-sdk` — abstract `Connector` base class + 5 mock implementations, all passing a shared contract-check test suite |
| Mock connectors clearly labelled, excluded from prod catalogue | ✅ | `is_simulator=True` on every mock catalogue entry; `list_catalog()` filters them out when `settings.is_production` |
| Tenants can connect/disconnect an integration | ✅ | `test_connect_integration_*`, `test_disconnect_integration_*`; manually verified live via browser (connect → appears in Connected table → detail page) |
| Credentials are encrypted, never returned by any API response | ✅ | Reuses Milestone 1's vault verbatim; `TenantIntegrationRead` schema has no secret field |
| Integration health is tracked | ✅ | `IntegrationHealth` row written on connect and after every sync; `/health` route + UI history list |
| Sync jobs run asynchronously and report status | ✅ | `POST /sync` enqueues a Celery task and returns immediately; `IntegrationSyncRun` transitions `running → success/failed`; verified via 4 consecutive live worker task runs with no errors |
| Asset inventory is built from sync data | ✅ | `ingest_sync_records()`; verified live — connecting the mock identity provider and syncing populated 3 real `Asset` rows visible in the UI |
| Assets deduplicate across repeated syncs | ✅ | `test_ingestion_is_idempotent_on_resync`; also manually verified — 4 repeated live syncs produced `created=0, updated=3` each time, never duplicate rows |
| Relationships resolve regardless of record order | ✅ | `test_relationship_resolves_regardless_of_yield_order` — cloud resource → cloud account `belongs_to` relationship |
| Criticality and ownership are settable and audited | ✅ | `PATCH /criticality`, `POST /owners` routes; `assets.criticality_updated` / `assets.owner_assigned` audit records; manually verified live (criticality change → change-history row appeared with old/new value) |
| Change tracking is append-only | ✅ | No UPDATE/DELETE RLS policy on `asset_changes`, same enforcement pattern as Milestone 1's `audit_logs` |
| Frontend: integrations catalogue + connect + assets list/detail | ✅ | `/integrations`, `/integrations/[id]`, `/assets`, `/assets/[id]` — built and manually driven end-to-end via headless-Chromium (Playwright) against the live stack |
| Backend tests pass | ✅ | **61/61** passing (`pytest -q` in `apps/api`), plus **12/12** in `packages/connector-sdk` |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 16/16 routes |

## Milestone 2 — Test Results (as actually executed in this session)

```
packages/connector-sdk: pytest -q     → 12 passed
apps/api: pytest -q                   → 61 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 16/16 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed:
- Booted a real Postgres/Redis/`uvicorn`/Celery-worker stack, drove it with `curl` and `psql` to confirm
  the connect → sync → ingest → asset-graph pipeline, and separately triggered 4 sequential sync tasks
  in one live worker process to confirm the worker-loop fix (below) actually holds under repeated load.
- Booted the Next.js dev server against that same live stack and drove it with a real headless-Chromium
  (Playwright) session through the full golden path: log in as the demo tenant owner → `/integrations` →
  connect the simulated identity provider → `/integrations/[id]` → trigger a sync → `/assets` (3 assets
  populated from the mock connector) → `/assets/[id]` → change criticality (`medium → high`, appears
  immediately in change history) → assign an owner (persists across a full page reload).

## Milestone 2 — Architecture Decisions (made or refined during implementation)

- **Worker/API dependency direction stays one-directional.** `apps/worker` depends on `apps/api`'s
  `core`/`db`/`modules` (unchanged from Milestone 1's `sys.path` approach), but `apps/api` must never
  import from `apps/worker` to enqueue a task. Solved with a lightweight Celery *client* in
  `apps/api/core/task_queue.py` that only needs a task name string and the broker URL
  (`Celery.send_task(...)`) — it never imports the worker's task registration module, so the dependency
  graph stays acyclic.
- **Celery queue consumption is opt-in per worker, not automatic.** Declaring a queue in
  `celery_app.conf` does not make a worker consume it — only `task_default_queue` is consumed unless the
  worker process is started with an explicit `-Q <queues>` flag. This is intentional Celery behaviour
  (it's how a production deployment would dedicate isolated workers to the `actions` queue per the
  architecture's safety-class isolation), but it means every worker-startup command in this repo
  (Dockerfile CMD, README) had to be updated explicitly rather than relying on config alone.
- **Significant, previously-latent bug found and fixed: Celery worker "attached to a different loop."**
  Each Celery task calls `asyncio.run()`, creating a fresh event loop per task. The process-level
  SQLAlchemy async engine's real connection pool (`pool_pre_ping=True`) hands out a connection whose
  asyncpg internals are still bound to the *first* task's now-closed loop on the second and subsequent
  tasks in the same worker process — this fails with "attached to a different loop." This bug existed
  since Milestone 1 but was never triggered because Milestone 1's worker tasks were only ever exercised
  once per worker process during testing; Milestone 2's more thorough live verification (multiple
  sequential sync tasks in one running worker) surfaced it. **Fix**: extend the same `NullPool` strategy
  already used for the pytest suite (which hit the identical root cause across test functions) to Celery
  worker processes too, gated by a `GRIDKEEP_WORKER_PROCESS=1` environment variable set in
  `apps/worker/celery_app.py` *before* `core.config`/`db.session` are imported (`apps/api/db/session.py`
  reads it at import time to pick the engine's pool class). Verified by triggering 4 consecutive sync
  tasks in one live worker process — all completed successfully with consistent, idempotent counts and
  no loop errors. This fix also silently corrects the same latent risk in Milestone 1's two maintenance
  tasks, though those were never observed to fail in practice.
- **`gridkeep-connector-sdk` is declared in `apps/api/pyproject.toml`'s dependency list for
  documentation purposes but is not fetchable from an index** — it must be `pip install -e`'d from
  `packages/connector-sdk` *before* installing `apps/api` itself (this order is what the Dockerfiles,
  README, and CI already do); once installed, `pip install -e ".[dev]"` finds it already satisfied
  locally and does not attempt to resolve it from a package index.

## Milestone 2 — Known Limitations

- **No real (non-simulator) connector has been implemented.** All 5 providers in the catalogue are
  mock/simulator connectors, clearly labelled as such and excluded from the catalogue in production.
  Building a first real integration (e.g. a real identity provider or EDR) is explicitly out of scope
  per the milestone plan and should be scoped as its own future milestone or backlog item.
- **No frontend automated tests were added for the new Integrations/Assets pages** — they were verified
  manually end-to-end via Playwright (see Test Results above) and pass lint/typecheck/build, matching
  the test-coverage level of Milestone 1's Dashboard/Settings pages (which also have no dedicated page
  tests), but this is a gap versus full coverage.
- **Docker Compose still not executed end-to-end** — the worker Dockerfile's CMD was updated with the
  `-Q` flag and `packages/connector-sdk` install step, but (as in Milestone 1) this has not been verified
  by actually building and running the containers, since no Docker daemon is available in this sandbox.
- **Relationship resolution requires both ends of a relationship to appear within records the tenant has
  already ingested** — a relationship record referencing an asset that no connector has ever reported
  (e.g. a cloud resource whose parent account isn't in scope) is silently skipped rather than creating a
  placeholder asset. This matches the spec's ingestion model but is worth confirming against real
  connector behavior when one is built.
- **Asset correlation/deduplication across *different* providers reporting the *same* real-world entity
  is not yet addressed** — dedup is currently keyed purely on `(tenant_id, identifier_type,
  identifier_value)` matching exactly; cross-provider identity resolution (e.g. matching an identity
  provider's user to an EDR's device owner by email) is Milestone 3+ scope (the correlation engine).

## Milestone 2 — Unresolved Risks

- Carried over from Milestone 1 (in-memory rate limiter, no second-approver support-access flow, no
  dependency/container/secret scanning in CI) — none of these were touched in Milestone 2 and remain
  open, tracked for Milestone 17 (Production Hardening).
- The worker-loop bug fixed in this milestone (see Architecture Decisions) is a reminder that
  single-shot testing of a worker task is not sufficient — any future worker task should be exercised
  at least twice in the same live process before being considered verified.

---

## Milestone 3 — Completed Work

### Backend — `modules/findings` (correlation engine and finding lifecycle)
- `rules.py`: seven fixed, code-defined correlation rules (a small registry, the same shape as the
  connector SDK's `REGISTRY` — not a tenant-configurable rules UI, which is reasonable future scope) —
  each a pure function over one asset's `attributes` dict:
  - `admin_without_mfa` (identity, critical) — administrator account with `mfa_enabled: false`
  - `dormant_user_account` (identity, medium) — no sign-in for 90+ days
  - `unencrypted_endpoint` (endpoint, high) — device disk not encrypted
  - `edr_agent_unresponsive` (endpoint, high) — EDR status not `healthy`
  - `stale_device_checkin` (endpoint, medium) — no check-in for 3+ days
  - `publicly_exposed_cloud_storage` (cloud, critical) — storage bucket with public access enabled
  - `backup_job_failed` (backup, high) — most recent backup run failed
  - These map directly onto the "demo scenario" data Milestone 2's mock connectors were already seeded
    with (an admin without MFA, a dormant account, an unencrypted laptop, an unresponsive/stale device,
    a public bucket, a failed backup) — the rules were designed to detect exactly that planted data, and
    live verification (below) confirms they do.
- `engine.py` (`run_correlation`): re-runs every rule against a tenant's current asset graph and
  reconciles the result against existing `Finding` rows, keyed on a unique `dedup_key`
  (`f"{rule_key}:{asset_id}"`) — idempotent and lifecycle-aware:
  - no existing finding + rule matches -> create one, status `open`
  - existing `open`/`assigned` finding still matches -> refresh evidence only
  - existing `accepted_risk` finding still matches -> refresh evidence, unless
    `accepted_risk_expires_at` has passed, in which case reopen it
  - existing `remediated`/`resolved` finding matches again -> reopen it (the condition came back)
  - existing `false_positive` finding matches again -> left alone permanently — the engine never
    overrides a human's dismissal
  - existing `open`/`assigned`/`accepted_risk` finding's rule no longer matches -> auto-resolve it
    (`status="resolved"`, `closed_at` set)
  - every transition writes an audit record (`findings.detected` / `.reopened` / `.auto_resolved` /
    `.accept_risk_expired`) via the same `modules.audit.service.record()` Milestone 1 built, with
    `actor_label="correlation_engine"` distinguishing engine-driven changes from human ones
- `scoring.py`: two intentionally simple, explainable formulas (not a sophisticated actuarial risk
  model) — `compute_finding_risk_score(severity, asset_criticality)` (0-100, per finding, used for
  sorting/display) and `compute_tenant_security_score(open_finding_severities)` (100 minus a fixed
  penalty per open finding's severity, floored at 0, used for the dashboard)
- `service.py`/`routes.py`: list (filterable by severity/status/asset/search), detail, a summary
  endpoint for the dashboard, and lifecycle actions — assign (validates the target is a real member of
  the tenant), accept-risk (reason + optional expiry), remediate (note), dismiss as false positive
  (reason), reopen, and a manual correlation trigger. All mutating routes are CSRF-protected,
  permission-gated (`findings.view` / `.assign` / `.accept_risk` / `.remediate`), and audited.
- `modules/audit/service.py` gained one new read helper, `list_for_target()`, so a finding's activity
  timeline reuses the existing generic `audit_logs` table (`target_type="finding"`) rather than
  Milestone 2's alternative of a dedicated append-only history table per module — avoids duplicating
  that pattern for what's fundamentally the same data shape.

### Worker (`apps/worker`) — correlation runs automatically after every sync
- `run_correlation` Celery task on the `correlate` queue (already declared in Milestone 1's queue list,
  never previously used for real work)
- `_run_integration_sync_async` now calls `enqueue_run_correlation(tenant_id)` immediately after a
  successful sync commits — findings stay current without a separate manual step. Enqueued via
  `core/task_queue.py`'s one-directional Celery client (same pattern as the sync-trigger route), not a
  direct function call, so a correlation failure can never roll back the sync that already committed.
- A manual "run correlation now" trigger remains available (`POST /api/findings/correlate`) for
  refreshing findings without waiting for a new sync — verified live via the UI.

### Frontend (`apps/web`)
- `/findings`: filterable table (severity, status, search), a manual "Run correlation now" button
  (permission-gated on `findings.remediate`)
- `/findings/[id]`: description, evidence (raw JSON from the triggering record), risk score, and
  lifecycle actions gated per-permission — assign (a one-click "assign to me" plus a teammate dropdown
  gated on `findings.assign` **and** `users.manage`, same `/api/users` constraint Milestone 2 hit for
  asset ownership), remediate, accept risk (with optional expiry date), dismiss as false positive, and
  reopen for any closed finding — plus a full activity timeline reusing the audit-log read helper above
- Dashboard: replaced Milestone 1's placeholder text (which literally said "lands in Milestone 3... once
  assets and findings exist to summarise") with a real security-score tile and open-findings-by-severity
  breakdown, sourced from `GET /api/findings/summary`
- Nav updated with a Findings link; active-state highlighting already covers nested detail routes from
  Milestone 2's fix

## Milestone 3 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| Correlation rules detect real risk conditions | ✅ | `test_identity_rules_*`, `test_endpoint_rules_*`, `test_cloud_and_backup_rules` — 7 rules, each verified against the actual mock connector data; also verified live (see below) |
| Correlation is idempotent | ✅ | `test_correlation_is_idempotent_on_rerun` — second run of unchanged state creates 0, updates existing; live verification showed no duplicate findings across a full connect→sync→correlate pass |
| Findings auto-resolve when the underlying condition clears | ✅ | `test_finding_auto_resolves_when_condition_clears` — re-ingesting a fixed device flips its finding to `resolved` |
| Remediated/resolved findings reopen if the condition regresses | ✅ | `test_remediated_finding_reopens_if_condition_still_present`; live-verified via the UI (remediate → reopen manually, and engine-driven reopening is exercised by the same test) |
| False-positive dismissals are never overridden by the engine | ✅ | `test_false_positive_is_never_reopened_by_the_engine` |
| Accepted-risk findings reopen after their expiry | ✅ | `test_accepted_risk_reopens_after_expiry`; findings accepted without an expiry persist indefinitely (`test_accepted_risk_without_expiry_persists_across_rerun`) |
| Findings can be assigned, remediated, accepted, dismissed, reopened via the API | ✅ | `test_findings_api.py` — 12 tests covering every lifecycle route; live-verified end-to-end via a real browser session |
| Every lifecycle transition is audited and visible as a timeline | ✅ | `test_finding_activity_records_lifecycle_events`; live-verified — the UI's Activity section showed `detected` → `assigned` → `remediated` in order for a real finding |
| Correlation runs automatically after a sync | ✅ | `_run_integration_sync_async` enqueues `run_correlation`; live-verified — connecting 4 providers and syncing each produced all 7 expected findings without a manual trigger |
| Manual correlation trigger works | ✅ | `test_trigger_correlation_enqueues_task`; live UI verification |
| Findings are tenant-isolated | ✅ | `test_findings_scoped_to_own_tenant`; RLS policy (`findings_tenant_isolation`) verified via migration round-trip |
| Assignment is restricted to actual tenant members | ✅ | `test_assign_finding_rejects_non_member` — a user_id from a different tenant is rejected with 422 |
| Dashboard shows a real, live security score | ✅ | Live-verified — connecting/syncing 4 mock providers produced a security score of 12/100 with the correct per-severity breakdown (2 critical, 3 high, 2 medium open findings), matching the documented formula exactly |
| Backend tests pass | ✅ | **81/81** passing (`pytest -q` in `apps/api`, up from 61 in Milestone 2 — 20 new tests), plus **12/12** in `packages/connector-sdk` |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 17/17 routes |

## Milestone 3 — Test Results (as actually executed in this session)

```
packages/connector-sdk: pytest -q     → 12 passed
apps/api: pytest -q                   → 81 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 17/17 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Celery-worker/Next.js stack, driven by a real
headless-Chromium (Playwright) session as the demo tenant owner:
- Connected all four data-producing mock providers (identity, endpoint, cloud, backup) via the UI,
  triggered a sync on each, and confirmed the worker chained a correlation run after every sync with no
  manual step — the Findings page showed all 7 expected findings (matching the rules above exactly)
  within seconds of the last sync completing.
- Verified the dashboard's security score updated live: 12/100, "At risk", with the exact per-severity
  breakdown (2 critical, 3 high, 2 medium) the formula predicts for those 7 findings.
- Drove a full finding lifecycle through the UI on real findings: assigned "Administrator account
  without MFA" to self, remediated it with a note, confirmed status/activity timeline updated correctly,
  reopened it, then separately accepted risk on "Dormant user account" with a reason and confirmed its
  status, resolution note, and activity entry all appeared correctly.

## Milestone 3 — Architecture Decisions (made or refined during implementation)

- **Correlation is a fixed, code-defined rule registry, not a tenant-configurable rules engine.** Same
  reasoning as the connector SDK's provider registry in Milestone 2 — a tenant-facing "write your own
  detection rule" UI is real future scope (and was never part of this milestone's plan), not something
  to half-build now. The registry pattern (`RULES`, `RULES_BY_ASSET_TYPE`) makes adding a rule later a
  pure-function addition with no engine changes required.
- **Two deliberately separate, simple scoring formulas, not one.** A per-finding "risk score" (how bad
  is this one issue) and a tenant-wide "security score" (how healthy is the tenant overall) answer
  different questions and were kept in distinct functions (`modules/findings/scoring.py`) with their own
  linear formulas, documented as intentionally not sophisticated — refining them (time-decay, exposure
  weighting, etc.) is reasonable future work, not a Milestone 3 requirement.
- **A finding's activity timeline reuses `audit_logs` rather than a new append-only table.** Milestone 2
  introduced `AssetChange` as a dedicated field-level diff ledger for a different reason (tracking
  attribute-value changes over time, which `audit_logs`' free-form `context` isn't well-shaped for).
  A finding's lifecycle timeline is a sequence of discrete named events (detected, assigned, remediated,
  ...) — exactly what `audit_logs` already models — so the only backend addition was a small read helper
  (`audit_service.list_for_target`) rather than a parallel table. Reuse over duplication where the
  existing shape already fits.
- **Correlation is chained after sync via the queue, not called directly from the sync task.** Keeps the
  same "enqueue, don't call" boundary Milestone 2 established between the API and worker — a correlation
  failure can never roll back or block the sync result that already committed, and the two concerns
  (ingesting data vs. deriving findings from it) stay independently retryable and independently
  observable in the Celery log.
- **Assignment validates real tenant membership at the service layer**, not just that a UUID was
  supplied — the same "don't trust client-supplied identifiers without a membership check" principle
  Milestone 1 applied to tenant-switching, applied here to a new lifecycle action.

## Milestone 3 — Known Limitations

- **No real (non-simulator) detection source.** All correlation rules run against Milestone 2's mock
  connector data. The rules themselves are real logic over real `attributes` dict shapes, not hardcoded
  to specific mock values, so they should generalize to a real connector's data once one exists — but
  that is unverified until a real connector is built.
- **No cross-provider identity resolution feeds correlation.** As noted in Milestone 2's known
  limitations, an asset is only ever what one connector reported; a rule cannot yet reason across
  multiple providers' view of "the same" real-world entity. This remains explicitly out of scope until
  the correlation/entity-resolution work referenced in the architecture module list.
- **No frontend automated tests were added for the new Findings pages** — same gap and same rationale as
  Milestone 2's Integrations/Assets pages: verified manually end-to-end via Playwright, passes
  lint/typecheck/build, but no dedicated Vitest coverage.
- **The security score and per-finding risk score are deliberately simple linear formulas**, documented
  as such in code and in this document — not a substitute for a real actuarial or ML-based risk model.
  Revisiting them with real customer feedback is reasonable future work.
- **No notification/alerting on new findings.** A critical finding appearing after a sync is only visible
  by looking at the Findings page or dashboard — no email/Slack/webhook notification exists yet. This is
  reasonable scope for a later automation-focused milestone (`cyber_autopilot`/`automations.manage` are
  already reserved permission/module keys for that work).
- **Findings are not yet linked into an incident-response workflow** — `incidents.*` permissions exist in
  the shared vocabulary but no incident model/routes exist yet; escalating a finding into an incident is
  out of scope for this milestone.

## Milestone 3 — Unresolved Risks

- Carried over from Milestones 1 and 2 (in-memory rate limiter, no second-approver support-access flow,
  no dependency/container/secret scanning in CI, Docker Compose still unverified end-to-end) — none were
  touched this milestone and remain open, tracked for Milestone 17 (Production Hardening).
- The simplicity of the scoring formulas (see Known Limitations) is a genuine product-judgment risk, not
  just a technical one — a tenant could see a low score driven by a handful of findings that don't
  reflect their actual risk tolerance. Flagged here rather than presented as a finished risk model.

## Pending Approvals

- This Milestone 3 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps are documented rather than hidden.
- Recommend explicit review of the two scoring formulas (`modules/findings/scoring.py`) specifically,
  since they're new product logic (not just infrastructure) that customers will see directly on their
  dashboard.

## Next Action

Awaiting your review. Once you're satisfied, send **`APPROVE MILESTONE 4`** to begin the next milestone.
