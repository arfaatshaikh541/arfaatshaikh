# GRIDKEEP Cyber OS — Project Status

Last updated: 2026-07-17 (Milestone 28 implementation)

## Current Milestone

**Milestone 28: Real Evidence File Storage + Real Email Dispatch** — implementation complete. This was the
fifth and last of five closable items identified from the user's "run all tests, tell me what's remaining,
and complete the project" instruction; see that milestone's section below for the full closeout summary.
Milestones 1 through 27 are complete and merged; their sections below are preserved as-is.

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
  **[Resolved in Milestones 13-14: Milestone 13 built real TOTP enrollment/login-challenge/step-up
  routes on top of exactly this schema; Milestone 14 then enforced `require_mfa_for_admins` and
  `require_step_up_for_disruptive_actions`. Found stale and corrected during Milestone 22's
  documentation-audit pass.]**
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

---

## Milestone 4 — Completed Work

### Connector SDK — action execution
- `Connector.execute_action()` added to the base class (default raises `NotImplementedError`, so a
  connector with no declared `supported_actions` never needs to implement it) plus a new `ActionResult`
  dataclass (`success`, `message`, `executed_at`).
- Implemented in every mock connector for its own declared actions: identity's `revoke_session` /
  `disable_user`, endpoint's `isolate_endpoint` / `request_scan`, cloud's `disable_public_sharing`,
  backup's `trigger_restore_test`. `threat_intel` declares no actions and needs no override.
- The shared contract-check suite (`testing/contract.py`) now calls `execute_action()` for every
  declared `ActionSpec` and asserts it returns an `ActionResult` — a connector can no longer declare an
  action it doesn't actually implement without failing its own contract test.

### Backend — `modules/actions` (action runs, playbooks, automation policy)
- **Models**: `ActionRun` (one attempt to execute a connector action against one asset — manual or
  playbook-triggered, with full lifecycle timestamps and an actor/approver trail), `Playbook` (maps a
  finding's `rule_key` to an `action_key`), `TenantAutomationSetting` (one row per tenant; absence means
  `observe`, the safest default).
- **`policy.py`**: a fixed, documented table (`AUTO_EXECUTE_MAX_SAFETY_CLASS`) mapping each of the five
  `AUTOMATION_MODES` (`observe` → `guided` → `balanced` → `autopilot` → `lockdown`, least to most
  autonomous) to a maximum safety class that auto-approves — the same "deliberately simple, explainable"
  approach Milestone 3 used for scoring, not a configurable rules engine.
- **`service.py`**: two distinct decision paths that were kept deliberately separate rather than
  unified, because they answer different questions:
  - `request_manual_action()` — a human explicitly asked for this action. Gated purely by *the actor's
    own permission*: `actions.execute_safe` lets anyone request any action, but it only executes
    immediately if the actor also holds `actions.approve_disruptive` or the action's safety class is
    0-1. The tenant's automation `mode` plays no part in a human-initiated request.
  - `evaluate_playbooks_for_findings()` — called after correlation for every finding newly created or
    reopened this run (not ones merely re-matched with unchanged status, so a playbook's action never
    re-fires on every correlation pass). Gated purely by the tenant's automation `mode` against the
    matched action's safety class. Never raises on a misconfigured playbook (e.g. an `action_key` the
    asset's current provider doesn't support) — a bad playbook is skipped for that finding, not a
    correlation-breaking error.
  - Both paths converge on the same `ActionRun` row shape and the same downstream execution task.
- **Routes**: `/api/actions/catalog` (available actions for an asset's connected provider),
  `/api/actions` (list/detail, filterable by status/asset/finding), `/api/actions/execute` (manual
  trigger), `/api/actions/{id}/approve` and `/reject`, `/api/playbooks` (CRUD, validates `rule_key`
  against the real correlation-rule registry), `/api/automation/settings` (get/set mode). All mutating
  routes CSRF-protected, permission-gated, and audited.
- `modules/audit/service.py`'s `list_for_target()` helper (added in Milestone 3) is reused as-is for
  nothing new here — Milestone 4 intentionally didn't add another parallel timeline table.

### Worker (`apps/worker`) — action execution and the automation chain
- `run_action` Celery task on the `actions` queue (declared since Milestone 1, unused until now):
  decrypts the credential, authenticates, calls `connector.execute_action()` against the asset's own
  identifier, records the result, and — if the run succeeded and is linked to a finding — automatically
  calls `findings_service.remediate_finding()` with an `automation_engine`-attributed note, closing the
  loop from detection through to a marked-fixed finding without a human touching it.
- `CorrelationSummary` gained `actionable_finding_ids` (findings created or reopened this run).
  `_run_correlation_async` evaluates playbooks against that list in the *same transaction* as
  correlation itself (both are cheap DB reads/writes on rows the transaction already touched), then
  enqueues `run_action` for every auto-approved run *after* that transaction commits — the same
  "enqueue, don't call directly" boundary Milestones 2 and 3 established, so a slow or failing action
  execution can never roll back correlation's own result.

### Frontend (`apps/web`)
- `/automation`: automation-mode picker (five radio options with the plain-language description from
  `policy.py`'s docstring, permission-gated on `automations.manage`), playbook CRUD (`playbooks.view` /
  `.manage`), and an action-run history table with approve/reject actions for anything
  `pending_approval` (`actions.view` / `actions.approve_disruptive`).
- Finding detail page gained a "Remediation actions" card: fetches the action catalog for the finding's
  asset, lets a permitted user run one directly, and shows the resulting run's status inline — the
  natural place a security analyst looking at a finding would want to fix it from.

## Milestone 4 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| Connectors can execute defensive actions, not just sync | ✅ | `execute_action()` on all 4 data-producing mocks; connector-sdk contract suite exercises every declared action — **12/12** passing |
| Automation mode governs auto-approval per safety class | ✅ | `test_evaluate_playbooks_*_mode_*` — observe creates nothing, guided never auto-approves, balanced auto-approves class ≤1, autopilot ≤3, lockdown everything; live-verified (see below) |
| Manual action execution is gated by actor permission, not tenant mode | ✅ | `test_manual_action_safety_class_*`, `test_execute_action_*` (API); a human with `actions.approve_disruptive` gets immediate execution of a disruptive action regardless of the tenant being in `observe` mode — live-verified |
| Playbooks map a finding rule to a remediation action | ✅ | `test_playbooks_crud`, `test_playbook_rejects_unknown_rule_key`; live-verified — created a real playbook, connected+synced a fresh tenant, watched it auto-trigger `trigger_restore_test` with no manual step |
| A successful automated action closes its finding | ✅ | Worker calls `remediate_finding` on `ActionRun` success; live-verified — the `backup_job_failed` finding flipped to `remediated` immediately after its auto-run `succeeded` |
| Action execution requires real approval for disruptive actions | ✅ | `test_execute_disruptive_action_without_approve_permission_is_pending`; live-verified with a `security_analyst` account (no `actions.approve_disruptive`) getting `pending_approval`, then a `tenant_owner` approving it |
| Playbooks never re-fire on an unchanged finding | ✅ | `actionable_finding_ids` only includes newly-created/reopened findings — verified via the idempotent-correlation tests carrying over from Milestone 3 plus manual inspection of `evaluate_playbooks_for_findings`'s call site |
| A misconfigured playbook doesn't break correlation | ✅ | `evaluate_playbooks_for_findings` catches `NotFoundError`/`ValidationAppError` per playbook match and continues; `test_evaluate_playbooks_no_matching_rule_key_creates_nothing` |
| Action runs and playbooks are tenant-isolated | ✅ | `test_actions_scoped_to_own_tenant`; RLS policies (`action_runs_tenant_isolation`, `playbooks_tenant_isolation`, `tenant_automation_settings_tenant_isolation`) verified via migration round-trip |
| Frontend: automation mode, playbooks, action-run approval, manual remediation | ✅ | `/automation`, Finding detail page's remediation card — built and live-verified end-to-end via headless Chromium |
| Backend tests pass | ✅ | **103/103** passing (`pytest -q` in `apps/api`, up from 81 in Milestone 3 — 22 new tests), plus **12/12** in `packages/connector-sdk` |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 18/18 routes |

## Milestone 4 — Test Results (as actually executed in this session)

```
packages/connector-sdk: pytest -q     → 12 passed
apps/api: pytest -q                   → 103 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 18/18 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Celery-worker/Next.js stack, driven by headless
Chromium:
- Set a tenant's automation mode to `balanced` and created a real playbook
  (`backup_job_failed` → `trigger_restore_test`) via the `/automation` UI *before* any sync, then
  connected and synced the backup provider on a **fresh** tenant. The chain ran with zero manual steps:
  sync → correlation created the `backup_job_failed` finding → the playbook matched → `balanced` mode
  auto-approved the class-1 action → the worker executed it → the finding flipped to `remediated`. Both
  the Automation page's action-run history and the Findings page reflected this correctly.
- Verified manual execution's permission model with two real accounts: a `tenant_owner` running a
  safety-class-2 action (`disable_public_sharing`) against the "publicly exposed cloud storage" finding
  got `approved` immediately (the actor holds `actions.approve_disruptive`); a `security_analyst`
  account (invited via the real invitation flow, no `approve_disruptive`) requesting the same action got
  `pending_approval`, which the owner then approved from the Automation page.
- Investigated an apparent duplicate-playbook/duplicate-action-run anomaly seen during exploratory
  testing; traced it to repeated manual test-script runs colliding on the same tenant, not a product
  bug — confirmed with a clean, isolated run (network-request logging showed exactly one
  `POST /api/playbooks` call producing exactly one row) before concluding the feature is correct.

## Milestone 4 — Architecture Decisions (made or refined during implementation)

- **Manual execution and playbook execution are gated by two different things on purpose.** A human
  explicitly clicking "run this action" has already made the risk judgment themselves — gating that on
  the tenant's ambient automation mode would be surprising (a `security_administrator` in an `observe`
  tenant should still be able to manually fix something). Gating *unattended* playbook-triggered
  execution on mode, and *attended* manual execution on the actor's own permission, are two independent
  axes that happen to share the same `ActionRun` model and execution path.
- **`observe` mode doesn't create `ActionRun` rows at all for playbook matches**, rather than creating
  them and leaving them permanently `pending_approval`. A tenant that hasn't opted into any automation
  shouldn't accumulate a growing backlog of actions nobody asked for; the finding itself is already the
  visible signal.
- **Playbook evaluation runs inside the same DB transaction as correlation, but action *execution* is a
  separate enqueued step.** The former is cheap in-transaction reads/writes; the latter calls out to a
  connector and can be slow or fail. Splitting them means a stuck or failing action execution can never
  roll back or block the correlation result that already committed — the same boundary Milestone 2 drew
  between ingesting a sync and Milestone 3 drew between correlating and running playbooks.
- **A successful action run auto-remediates its linked finding** rather than leaving the human to notice
  the action succeeded and manually mark it fixed. This is the payoff of the whole milestone — "detect →
  decide → act → confirm" with no required human step in the `balanced`/`autopilot`/`lockdown` path —
  and was verified live, not just asserted in a unit test.
- **`ActionRun`/`TenantAutomationSetting`/`Playbook` actor columns are real foreign keys to `users.id`**,
  a step stricter than Milestone 2's `TenantIntegration.created_by_user_id` (which is a bare UUID column
  with no FK). Worth noting as a small inconsistency in the codebase's history, not something retrofitted
  onto the earlier table — Milestone 4's actor trail (who requested, who approved) is load-bearing for
  the approval workflow in a way Milestone 2's was not.

## Milestone 4 — Known Limitations

- **No real (non-simulator) action execution has been implemented** — same caveat as every other
  milestone's mock-only connectors. The `execute_action()` contract is real and enforced by the
  connector-sdk test suite, but unverified against an actual third-party API.
- **No default/starter playbooks are seeded for any tenant**, including the demo tenant — a tenant (or
  this session's manual testing) must create its own. This matches the "tenant owns their automation
  policy" principle used elsewhere (nothing disruptive happens without explicit tenant configuration),
  but means the demo experience requires a manual playbook-creation step to show automation in action.
- **No retry/backoff on a failed `ActionRun`.** A failed action (provider rejected it, or an
  infrastructure error) is recorded as `failed` with a result message but nothing automatically retries
  it — a human must notice and re-trigger manually. Reasonable v1 scope; a retry policy is a natural
  follow-up once real provider failure modes are observed.
- **Playbooks match on `rule_key` alone, not on asset attributes beyond what the rule itself already
  encodes.** A tenant cannot yet say "auto-remediate `backup_job_failed` only for backups tagged
  critical" — that's a reasonable filtering enhancement for a future milestone, not required here.
- **No notification when an action is `pending_approval`.** Same gap noted in Milestone 3 for new
  findings — an approver only sees a pending action by visiting the Automation page. Real
  notification/alerting is out of scope until a dedicated automation-focused milestone.

## Milestone 4 — Unresolved Risks

- Carried over from Milestones 1-3 (in-memory rate limiter, no second-approver support-access flow, no
  dependency/container/secret scanning in CI, Docker Compose still unverified end-to-end, the scoring
  formulas' simplicity) — none were touched this milestone and remain open.
- **Automated action execution is inherently higher-stakes than anything shipped in Milestones 1-3** —
  this is the first milestone where GRIDKEEP can take a real, provider-facing action without a human in
  the loop (in `balanced` mode and above). The safety-class/automation-mode policy is deliberately
  conservative and documented, and every path was live-verified, but this is the kind of feature that
  most rewards a careful second look before any tenant is allowed to enable `autopilot` or `lockdown` in
  production.

## Milestone 4 — Pending Approvals

- This Milestone 4 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps are documented rather than hidden.
- Recommend explicit review of `modules/actions/policy.py` (the automation-mode safety-class table) and
  the manual-vs-playbook gating split in `modules/actions/service.py` specifically — this milestone is
  the first to let the platform act on a tenant's behalf without a human clicking a button, and both of
  those are where that boundary is actually enforced.

---

## Milestone 5 — Completed Work

### Backend — `modules/incidents` (declared → investigating → contained → resolved → closed)
- **Models**: `Incident` (title, description, severity, status, declared/assigned-to actors, declared/
  resolved/closed timestamps, closure summary) plus two lightweight join tables — `IncidentFinding` and
  `IncidentAsset` — linking an incident to zero or more findings/assets. An incident is explicitly a
  *coordinating narrative* over findings/assets, not a control mechanism over them: closing an incident
  never changes the status of any linked finding, since some may already be remediated, some
  accepted-risk, some deliberately left open.
- **No dedicated timeline table.** Same decision Milestone 3 made for a finding's activity timeline —
  an incident's history (declared, status changed, note added, finding/asset linked, closed, reopened)
  is the same shape `audit_logs` already models, so it reuses `modules.audit.service.list_for_target()`
  rather than adding a fourth table.
- **`declare_incident()`**: creates the incident and, for every `finding_id` passed at declaration time,
  also links that finding's own asset automatically — escalating a finding is inherently about the asset
  it concerns, so that asset shouldn't have to be linked as a second manual step. The same auto-link
  happens on `link_finding()` when called later, not just at declaration.
- **Status lifecycle enforcement**: `update_status()` only accepts `investigating`/`contained`/
  `resolved` (never `declared` or `closed` directly — those have their own dedicated entry/exit routes)
  and refuses to run at all once an incident is `closed`. `close_incident()` requires a closure summary
  and refuses a second close. `reopen_incident()` only accepts a `closed` incident and moves it back to
  `investigating`.
- **Routes**: `GET/POST /api/incidents`, `GET /api/incidents/summary`, `GET /api/incidents/{id}`
  (+`/activity`), `PATCH /api/incidents/{id}` (details/assignee — assignee validated as a real tenant
  member, same pattern Milestone 3 used for finding assignment), `PATCH .../status`,
  `POST .../notes`, `.../link-finding`, `.../link-asset`, `.../close`, `.../reopen`. All mutating routes
  CSRF-protected, permission-gated, and audited.
- **Scoping decision: `evidence.*` permissions are deliberately unused in this milestone.** The
  permission matrix already distinguishes them from `incidents.*` — `compliance_manager` holds
  `evidence.view`/`evidence.export` but *not* `incidents.view`, which only makes sense if evidence is a
  decoupled concept (a future Evidence Platform pillar, matching the README tagline's ordering:
  "incident-response centre, evidence platform, ...") rather than part of incident detail. Gating
  incident routes on `evidence.*` would have been a plausible-looking but incorrect reading of the
  vocabulary; every incident route is gated purely on `incidents.*`.

### Frontend (`apps/web`)
- `/incidents`: filterable list (status, severity) plus an inline "Declare incident" form
  (`incidents.declare`).
- `/incidents/[id]`: details, status-transition buttons, a note form, linked findings/assets (with
  dropdowns to link more, pre-filtered to exclude what's already linked), close/reopen, assignee picker,
  and a full activity timeline — all permission-gated per action (`incidents.manage` / `.close`).
- Finding detail page gained an "Escalate to incident" button (`incidents.declare`): declares a new
  incident pre-populated from the finding's own title/description/severity, pre-linked to that finding
  (and therefore its asset), and navigates straight to the new incident.
- Dashboard gained an "Open incidents" tile (open count + severity breakdown, mirroring Milestone 3's
  security-score tile), gated on `incidents.view`.

## Milestone 5 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| Incidents can be declared, manually or from a finding | ✅ | `test_declare_incident_sets_declared_status`, `test_declare_incident_from_finding_links_asset`; live-verified — escalated a real "publicly exposed cloud storage" finding into an incident via the UI |
| Escalating a finding auto-links its asset | ✅ | `test_declare_incident_with_finding_links_findings_asset_too`, `test_link_finding_and_asset_endpoints`; live-verified in the same run |
| Linking a finding/asset is idempotent | ✅ | `test_link_finding_is_idempotent`; API test confirms re-linking an already-linked asset doesn't duplicate |
| Status moves through investigating/contained/resolved, tracks resolved_at | ✅ | `test_update_status_sets_resolved_at`; live-verified via the UI's status buttons |
| A closed incident can't have its status changed directly, or be closed twice | ✅ | `test_close_then_status_change_rejected` |
| Reopen only works on a closed incident, and clears closed_at | ✅ | `test_reopen_incident`, `test_reopen_rejects_non_closed_incident`; live-verified |
| Closing an incident never mutates linked findings' own status | ✅ | Verified by code inspection (`close_incident` touches only the `Incident` row) and live — the linked finding stayed `open` throughout the incident's full close/reopen cycle |
| Assignment is restricted to actual tenant members | ✅ | `test_update_incident_validates_assignee_membership` |
| A full activity timeline is recorded and visible | ✅ | `test_incident_lifecycle_status_notes_close_reopen` asserts all 5 event types present; live-verified — the UI showed declared → status_changed → note_added → closed → reopened in correct order |
| `security_analyst` can declare but not manage or close | ✅ | `test_security_analyst_can_declare_but_not_manage_or_close` — a real invited member with that role got 403 on status-change and close |
| Incidents are tenant-isolated | ✅ | `test_incidents_scoped_to_own_tenant`; RLS policies verified via migration round-trip |
| Dashboard and list summaries exclude closed incidents | ✅ | `test_incident_summary_excludes_closed`, `test_incident_summary_endpoint`; live-verified — the dashboard tile matched the incidents list exactly |
| Backend tests pass | ✅ | **121/121** passing (`pytest -q` in `apps/api`, up from 103 in Milestone 4 — 18 new tests), plus **12/12** in `packages/connector-sdk` |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 19/19 routes |

## Milestone 5 — Test Results (as actually executed in this session)

```
packages/connector-sdk: pytest -q     → 12 passed
apps/api: pytest -q                   → 121 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 19/19 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Celery-worker/Next.js stack, driven by headless
Chromium: connected and synced the cloud provider on a fresh tenant, opened the resulting "publicly
exposed cloud storage" finding, clicked "Escalate to incident" and confirmed it landed on a new incident
pre-linked to that finding and its asset; moved the incident through `investigating`, added a note,
closed it with a summary, reopened it, and confirmed the activity timeline showed all five events in the
correct order; confirmed the dashboard's "Open incidents" tile and the `/incidents` list agreed exactly.

## Milestone 5 — Architecture Decisions (made or refined during implementation)

- **An incident coordinates findings/assets; it does not control them.** Explicitly decided against
  auto-remediating or auto-accepting-risk on linked findings when an incident closes — some findings
  might already be fixed via Milestone 4 automation, some might be deliberately accepted risk, and some
  might remain genuinely open after the incident narrative itself is closed (e.g. "the breach is
  contained, but the underlying misconfiguration still needs a follow-up ticket"). Conflating "this
  incident is over" with "every finding it touched is now fine" would have been a false signal.
- **`evidence.view`/`evidence.export` are reserved, not used, in this milestone** — see the Completed
  Work section above for the reasoning from the permission matrix itself. This was a genuine scoping
  fork: it would have been easy to gate the incident timeline or a "close" action on `evidence.export`
  and have it look plausible, but the matrix's own data (`compliance_manager` lacking `incidents.view`)
  rules that reading out.
- **Incident timeline reuses `audit_logs` again, not a new table** — third consecutive milestone
  (Findings, then implicitly Actions via the same audit trail, now Incidents) reusing the same
  append-only ledger + `list_for_target()` helper rather than inventing a parallel per-module history
  table each time. This is now clearly the established pattern for "a sequence of discrete named events
  about one entity," not a one-off.
- **`link_finding`/`link_asset` are idempotent by design**, not by catching a unique-constraint
  violation — they check for an existing row first and no-op if found. This avoids relying on exception
  handling for a normal, expected code path (a user might reasonably click "link" on something already
  linked) and keeps the operation's happy path and its "already done" path equally cheap and equally
  safe to call from both `declare_incident` and the standalone link routes.

## Milestone 5 — Known Limitations

- **No incident-response playbooks or automation.** Unlike findings, an incident's lifecycle is entirely
  human-driven — there's no equivalent of Milestone 4's automation engine that, say, auto-declares an
  incident when N critical findings appear together, or auto-contains an asset when an incident reaches
  a certain severity. This is a reasonable and likely valuable future integration between the two
  milestones, not attempted here to keep this milestone's scope coherent.
- **No file/attachment evidence** — the timeline is text notes and structured events only; there's no
  way to attach a screenshot, log export, or other artifact to an incident. That's squarely the future
  Evidence Platform milestone's scope (see the `evidence.*` scoping decision above).
- **No incident severity auto-escalation** from its linked findings — declaring an incident at "medium"
  and later linking a "critical" finding does not change the incident's own severity; a human sets and
  changes it explicitly via `PATCH /api/incidents/{id}`. Simple and predictable, but a tenant might
  reasonably expect some correlation.
- **No SLA/response-time tracking** (e.g. time-to-acknowledge, time-to-contain) — `declared_at`/
  `resolved_at`/`closed_at` are recorded, so this is derivable later without a schema change, but no
  metric or reporting surface computes it yet.
- **No frontend automated tests were added for the new Incidents pages** — same gap and rationale as
  every prior milestone's new pages: verified manually end-to-end via Playwright, passes
  lint/typecheck/build, but no dedicated Vitest coverage.

## Milestone 5 — Unresolved Risks

- Carried over from Milestones 1-4 (in-memory rate limiter, no second-approver support-access flow, no
  dependency/container/secret scanning in CI, Docker Compose still unverified end-to-end, the scoring
  formulas' simplicity, the inherent stakes of unattended action execution) — none were touched this
  milestone and remain open.
- The `evidence.*` scoping decision (deliberately unused here) is a judgment call based on reading the
  permission matrix's own internal consistency, not an explicit instruction — flagged for your review
  rather than treated as beyond question, since it shapes how the future Evidence Platform milestone
  gets scoped.

## Milestone 5 — Pending Approvals

- This Milestone 5 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps are documented rather than hidden.
- Recommend explicit review of the `evidence.*` scoping decision specifically (see Architecture
  Decisions) — it's an interpretation of the existing permission vocabulary rather than something
  explicitly specified, and it sets a precedent for how the future Evidence Platform milestone relates
  to Incident Response.

---

## Milestone 6 — Completed Work

### Connector SDK — `mock_backup` demo scenario (`packages/connector-sdk`)
- Extended the existing mock backup connector's `nightly-file-server-backup` job (no new records, no
  identifier changes — every prior test that hardcodes `mock-backup-job-001`/`-002` or the job count
  keeps working unmodified): flipped `immutable` from `True` to `False` and moved `last_run_at` from
  10 hours ago to 60 hours ago, while leaving `last_run_status: "success"`. This is a deliberate "looks
  healthy but isn't ransomware-resilient" scenario — the job *succeeded*, so a naive "did my backup run
  OK?" check would miss both problems entirely. `nightly-database-backup` (already failing, from
  Milestone 3) is untouched.

### Backend — two new correlation rules (`modules/findings/rules.py`)
- **`backup_not_immutable`** (`backup_job`, severity `high`): fires when `attributes.immutable is False`.
  An immutable backup can't be altered or deleted by ransomware or a malicious actor before it's needed
  for recovery; a mutable one can.
- **`backup_job_stale`** (`backup_job`, severity `medium`): fires when `last_run_at` is older than a new
  `BACKUP_STALE_THRESHOLD = timedelta(hours=48)` constant (mirrors the existing
  `DORMANT_ACCOUNT_THRESHOLD`/`STALE_DEVICE_THRESHOLD` pattern in the same file). No news for 48+ hours
  means no confidence a *recent* recovery point exists.
- Both rules ride the existing correlation engine (`modules/findings/engine.py`) unmodified — the engine
  already evaluates every rule registered for an asset's type, so a single `backup_job` asset can now
  carry up to three simultaneous findings (`backup_job_failed`, `backup_not_immutable`,
  `backup_job_stale`), each with its own lifecycle (open/resolved/reopened) independent of the others.
  This gets the new risks the entire existing findings/correlation/actions/incidents pipeline for free —
  a `backup_not_immutable` finding can be assigned, accepted-risk, remediated, actioned via a playbook,
  or escalated into an incident exactly like any other finding, with no new code required for any of it.

### Backend — `modules/resilience` (new, no migration)
- **Deliberately has no models or migration of its own.** A `backup_job` is already an `Asset` (as
  produced by any backup-platform connector); this module is pure read-only aggregation over existing
  `Asset` rows filtered to `asset_type.key == "backup_job"`, not a new system of record.
- **`get_resilience_summary()`**: for each backup-job asset, computes a per-job score starting at 100
  with a fixed deduction for each of three independent risk factors — last run didn't succeed (-50), not
  immutable (-30), stale beyond 48 hours or no timestamp at all (-20) — floored at 0. The tenant-wide
  **Recovery Confidence Score** is the plain average of per-job scores, or `None` when the tenant has no
  backup jobs yet (explicitly distinct from "score is 0" — nothing to score isn't the same as everything
  being broken). Mirrors Milestone 3's `scoring.py` in spirit: simple, linear, explainable to a customer,
  not a sophisticated backup-maturity model.
- **Route**: `GET /api/resilience/summary`, gated on `assets.view` — chosen because no dedicated
  permission namespace exists for this domain (`security-contracts` has a `backup_resilience` *module*
  key but no `resilience.*`/`backup.*` *permissions*), and `assets.view` is already the broadest-held
  permission in the matrix, including for `executive_viewer`.

### Frontend (`apps/web`)
- New `/resilience` page: Recovery Confidence Score card (score, tone badge, job/immutable/stale/failed
  counts) plus a per-job table (last run status, immutable, freshness, individual score).
- Dashboard gained a "Recovery confidence" tile (score, backup job count, link to `/resilience`), gated
  on `assets.view`, inserted between the existing "Open incidents" tile and the 3-column status grid.
- Nav gained a "Resilience" item, after Automation.

## Milestone 6 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| A backup job that succeeded but isn't immutable is flagged | ✅ | `test_correlation_flags_not_immutable_and_stale_backup_jobs`, `test_cloud_and_backup_rules`; live-verified — "Backup job is not immutable" (High) appeared on `nightly-file-server-backup` |
| A backup job that hasn't run in 48+ hours is flagged, independent of status | ✅ | Same tests; live-verified — "Backup job has not run recently" (Medium) appeared on the same job alongside the immutability finding |
| A single backup job can carry multiple independent findings | ✅ | Live-verified — `nightly-file-server-backup` carried both `backup_not_immutable` and `backup_job_stale` simultaneously; existing `backup_job_failed` on `nightly-database-backup` unaffected |
| Recovery Confidence Score computes correctly from real asset data | ✅ | `test_resilience_summary_scores_mock_backup_jobs` (asserts the exact 50/100 score and per-job breakdown); live-verified — UI matched the test's expected numbers exactly on a fresh tenant |
| No backup jobs yet → score is `None`, not 0 or an error | ✅ | `test_resilience_summary_empty_tenant_has_no_score` |
| Resilience summary is tenant-isolated | ✅ | `test_resilience_summary_scoped_to_own_tenant` |
| Resilience endpoint is reachable by the broad `assets.view` permission | ✅ | `test_resilience_summary_endpoint`; live-verified as `tenant_owner` |
| No regressions to Milestones 2-5 from the mock connector data change | ✅ | Full backend suite passes (126/126, up from 121); the one pre-existing test whose *count* was directly affected (`test_cloud_and_backup_rules`) was updated with the new expected count and explicit new-rule assertions, not silently left wrong |
| No new database migration required | ✅ | `alembic current` unchanged at `c4a8de62f1b3` before and after — `modules/resilience` has no models |
| Backend tests pass | ✅ | **126/126** passing (`pytest -q` in `apps/api`, up from 121 — 5 new tests), plus **12/12** in `packages/connector-sdk` |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 20/20 routes |

## Milestone 6 — Test Results (as actually executed in this session)

```
packages/connector-sdk: pytest -q     → 12 passed
apps/api: pytest -q                   → 126 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 20/20 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Celery-worker/Next.js stack, driven by headless
Chromium, on a fresh tenant: connected the `mock_backup` integration, triggered a sync, and confirmed
the Findings page showed all three backup findings (`Backup job is not immutable` — High,
`Backup job has not run recently` — Medium, both on `nightly-file-server-backup`, and the pre-existing
`Backup job failed` — High on `nightly-database-backup`); confirmed `/resilience` showed a Recovery
Confidence Score of exactly 50/100 with the correct per-job breakdown (1 of 2 immutable, 1 of 2 stale, 1
of 2 failed last run); confirmed the dashboard's "Recovery confidence" tile matched the `/resilience`
page exactly, and that the dashboard's security score (70/100) correctly reflected the two new High and
one new Medium findings' penalty.

## Milestone 6 — Architecture Decisions (made or refined during implementation)

- **A new risk domain does not need a new detection system.** `backup_not_immutable` and
  `backup_job_stale` are just two more `RuleDefinition`s in the same fixed registry Milestone 3 built —
  no parallel "resilience findings" table, no separate evaluation loop. The correlation engine was
  already generic over asset type and rule count per asset; extending it required zero engine changes.
- **A rollup module doesn't need a system of record if the underlying facts already have one.**
  `modules/resilience` has no models, no migration, and no new tables — a backup job's health is fully
  described by its `Asset.attributes`, which the connector already writes. Building a new "backup job
  posture" table that duplicates that data would create a second source of truth to keep in sync for no
  benefit.
- **Gated on `assets.view`, not a new permission.** `security-contracts` reserves the module key
  `backup_resilience` for later (executive reporting / entitlements), but defining new
  `resilience.*`/`backup.*` permissions now, with nothing yet to differentiate "can view resilience" from
  "can view assets," would be speculative. `assets.view` is already correct and already broadly granted.
- **Missing `last_run_at` counts as stale, not as "unknown/skip."** A backup job with no last-run
  timestamp at all gets the same `-20` penalty as one whose last run is provably old — deliberately
  pessimistic, since "we don't know when this last ran" is not meaningfully safer than "this hasn't run
  recently" from a recovery-confidence standpoint.
- **The connector data-shape change was scoped to be additive-only.** Before editing `mock_backup.py`,
  confirmed via `grep` across `apps/api/tests` and `packages/connector-sdk/tests` that no test hardcodes
  the specific attribute values being changed (only the one test whose *finding count* depends on them,
  `test_cloud_and_backup_rules`, needed updating) — record identifiers, counts, and the job's
  `last_run_status` were left untouched, so the blast radius was the demo scenario's realism, not the
  fixture's shape.

## Milestone 6 — Known Limitations

- **No connector actually enforces immutability or restore testing** — `trigger_restore_test` (added in
  Milestone 4) exists as an action but nothing in this milestone wires a playbook to it automatically
  based on the new findings; a tenant has to create that playbook themselves via the existing Automation
  page, the same way they would for any other rule/action pairing.
- **Per-job score has no severity-weighted or recency-weighted variant** — a job that failed once
  yesterday and one that's been failing for a month score identically. Same "deliberately simple, not
  actuarial" tradeoff Milestone 3 made for finding/tenant scoring, applied consistently here.
- **Only one connector (`mock_backup`) produces `backup_job` assets** — the resilience summary and both
  new rules work against any connector that emits the `backup.job` record type with the same attribute
  shape, but only the mock one exists today; a real backup-platform connector (Veeam, Datto, etc.) is
  future integration work, not part of this milestone.
- **No historical trend for the Recovery Confidence Score** — only the current snapshot is exposed; there
  is no time-series of how the score has moved, matching the same gap called out for the security score
  in Milestone 3.
- **No frontend automated tests were added for the new Resilience page** — same gap and rationale as
  every prior milestone's new pages: verified manually end-to-end via Playwright, passes
  lint/typecheck/build, but no dedicated Vitest coverage.

## Milestone 6 — Unresolved Risks

- Carried over from Milestones 1-5 (in-memory rate limiter, no second-approver support-access flow, no
  dependency/container/secret scanning in CI, Docker Compose still unverified end-to-end, the scoring
  formulas' simplicity, the inherent stakes of unattended action execution, the `evidence.*` scoping
  decision) — none were touched this milestone and remain open.
- The per-job scoring weights (-50/-30/-20) are a judgment call, not derived from any stated
  specification — flagged for your review the same way Milestone 3's severity-penalty table was, since
  it directly determines what "Needs attention" vs. "At risk" means to a customer.

## Milestone 6 — Pending Approvals

- This Milestone 6 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps are documented rather than hidden.
- Recommend explicit review of the per-job scoring weights (see Architecture Decisions) and of the
  `assets.view` gating choice for `/api/resilience/summary` — both are interpretations made in the
  absence of an explicit specification for this milestone.

---

## Milestone 7 — Completed Work

### Backend — `modules/compliance` (frameworks, controls, and polymorphic evidence)
- **Two-tier catalogue, same shape as `AssetType`/`Asset`**: `ComplianceFramework` and `ComplianceControl`
  are platform-wide, seeded, non-tenant-scoped tables (no RLS, same as `asset_types`) — a small,
  representative subset of two well-known frameworks (SOC 2 Type II's Security/Common-Criteria category,
  5 controls; ISO/IEC 27001:2022, 5 representative Annex A controls), seeded idempotently via a new
  `_upsert_compliance_catalog()` in `seed/bootstrap.py`. Not exhaustive or certification-ready — it
  exists to give the module real, structurally correct data, the same role Milestone 2's minimal
  `AssetType` seed played for the asset graph.
- **`TenantControlStatus`** is the tenant-scoped half: a tenant's own assessment (`met`/`partial`/
  `not_met`/`not_applicable`) of one control, created lazily — a control with no row yet is treated as
  `not_met` by the service layer, so the table only ever holds controls a tenant has actually touched.
- **Scoring**: a framework's score is `met / total * 100`, where `partial` counts as half credit and
  `not_applicable` controls are excluded from the denominator entirely (not counted against the tenant).
  A framework with nothing left to count (all `not_applicable`, or no controls) scores 100, not 0 —
  "nothing to assess" is distinct from "everything failing." The overall score is the plain average of
  every framework's score. Deliberately simple and linear, mirroring `modules.findings.scoring` and
  `modules.resilience.service` in spirit — not an actuarial audit model.
- **`EvidenceRecord`**: a structured evidence entry (title, description, and either a URL or a free-text
  note) with a polymorphic `target_type`/`target_id` — the same shape `audit_logs` already uses — so
  evidence can attach to a `compliance_control` or an `incident` without a separate join table per
  target. **Deliberately not a file upload**: there is no object-storage client wired up anywhere in this
  codebase (the `object_storage_*` settings in `core/config.py` have sat unused since Milestone 1), so
  real document attachment would have meant standing up and testing MinIO/S3 integration untested in
  this environment — future work, not faked here with an unverified upload path.
- **No standalone `evidence.manage` permission — this is deliberate, not an oversight.** The permission
  matrix already splits it: `incident_responder` holds `evidence.view`/`evidence.export` but no
  `compliance.*`, while `security_administrator` holds `incidents.manage` but no `compliance.*` either.
  The only reading that makes both consistent is that **creating evidence is gated by whatever
  permission already manages its target** — `compliance.manage` for a compliance control, `incidents.
  manage` for an incident — while `evidence.view`/`evidence.export` are the uniform read-side
  permissions that apply regardless of what the evidence is attached to. `modules.compliance.service.
  TARGET_MANAGE_PERMISSION` encodes this mapping explicitly; the route layer checks it dynamically
  per-request rather than using a single static `require_permission` dependency, since the correct
  permission depends on the request body's `target_type`.
- **Routes**: `GET /api/compliance/frameworks` and `/summary` (`compliance.view`), `PATCH /api/compliance/
  controls/{id}` (`compliance.manage`), `GET/POST /api/evidence` and `DELETE /api/evidence/{id}`
  (permission resolved per-target as above), `GET /api/evidence/export` (`evidence.export` — returns a
  structured JSON manifest of a target's evidence, a documented lightweight stand-in for a future PDF/
  zip export bundle).

### Frontend (`apps/web`)
- New `/compliance` page: one card per framework (score, tone badge), each control as a row with a
  status dropdown + note field (gated `compliance.manage`; read-only for `compliance.view`-only roles),
  and a per-control expandable evidence section.
- New shared `EvidenceList` component (`components/EvidenceList.tsx`) — list + add + remove evidence for
  any `target_type`/`target_id`, reused unmodified on both the Compliance page (per-control) and the
  Incident detail page (per-incident), matching the backend's polymorphic design.
- Incident detail page gained an "Evidence" card (gated `evidence.view`, manage actions gated by whatever
  the caller already passes as `canManage` — `incidents.manage` in this context).
- Dashboard gained a "Compliance" tile (overall score, framework count, link to `/compliance`), gated on
  `compliance.view`, inserted after the "Recovery confidence" tile.
- Nav gained a "Compliance" item, after Resilience.

## Milestone 7 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| Two frameworks are seeded with real controls | ✅ | `test_frameworks_seeded_with_five_controls_each_default_not_met`; live-verified — both SOC 2 and ISO 27001 rendered with 5 controls each on a fresh tenant |
| Updating a control's status recomputes its framework's score correctly | ✅ | `test_update_control_status_upserts_and_recomputes_score`, `test_partial_status_counts_as_half_credit`; live-verified — marking one control "met" moved the ISO score from 0 to 20 |
| `not_applicable` controls are excluded from the score, not counted as failing | ✅ | `test_not_applicable_controls_excluded_from_score` |
| Overall compliance score averages every framework's score | ✅ | `test_compliance_summary_averages_framework_scores`; live-verified — dashboard tile showed 10/100 matching the two frameworks' 20 and 0 |
| Evidence can attach to a compliance control | ✅ | `test_create_evidence_for_compliance_control`; live-verified — "Access review sign-off" attached and listed under its control |
| Evidence can attach to an incident | ✅ | `test_evidence_create_permission_depends_on_target`; live-verified — "Login IP geolocation report" attached to a live-declared incident |
| Evidence creation permission depends on the target, not a single `evidence.manage` | ✅ | `test_evidence_create_permission_depends_on_target` — `incident_responder` succeeded attaching evidence to an incident (`incidents.manage`) and got 403 attaching to a compliance control (no `compliance.manage`) |
| A role without `compliance.manage` cannot change control status | ✅ | `test_security_analyst_cannot_manage_compliance` |
| Evidence is tenant-isolated | ✅ | `test_evidence_scoped_to_own_tenant` |
| Evidence list/export endpoints work and are permission-gated | ✅ | `test_evidence_list_and_export_endpoints` |
| Backend tests pass | ✅ | **144/144** passing (`pytest -q` in `apps/api`, up from 126 — 18 new tests), plus **12/12** in `packages/connector-sdk` |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 21/21 routes |

## Milestone 7 — Test Results (as actually executed in this session)

```
packages/connector-sdk: pytest -q     → 12 passed
apps/api: pytest -q                   → 144 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 21/21 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Celery-worker/Next.js stack, driven by headless
Chromium, on a fresh tenant: opened `/compliance` and confirmed both seeded frameworks rendered with all
10 controls; set a control to "met" with a note and confirmed its framework's score updated live (0 →
20/100) with no page reload; attached a "note"-type evidence record to that control and confirmed it
appeared in the control's evidence list; confirmed the dashboard's new "Compliance" tile matched the
`/compliance` page's overall score exactly (10/100, averaging 20 and 0); declared a fresh incident via
the UI, opened its detail page, and attached a second evidence record directly to the incident, using the
same shared `EvidenceList` component. One real bug was caught and fixed during this pass: the dev
database's platform catalogue hadn't been re-seeded after the new migration ran, so `/compliance` first
rendered as a blank page with an empty framework list — running `python -m seed.bootstrap` (the existing,
idempotent, safe-everywhere catalogue seed) resolved it immediately; this is an operational step already
documented in the README's setup instructions, not a code defect.

## Milestone 7 — Architecture Decisions (made or refined during implementation)

- **Evidence's create/delete permission is resolved per-target at the route layer, not via a single
  static dependency.** Every other mutating route in this codebase uses `Depends(require_permission(...))`
  with one fixed permission string. Evidence can't, because the correct permission depends on the
  request's own `target_type` field. `TARGET_MANAGE_PERMISSION` in `modules.compliance.service` makes
  this mapping an explicit, testable dictionary rather than scattering `if target_type == ...` permission
  logic inline — and the route still raises the same `AuthorizationError` shape every other 403 in the
  app raises, so the client-side error handling needed no special-casing.
- **Compliance frameworks/controls are platform-wide catalogue tables, deliberately without RLS** — the
  same reasoning as `asset_types`: every tenant reads the identical control definitions, so there is
  nothing tenant-specific to isolate at that layer. Isolation instead lives one level down, in
  `TenantControlStatus` and `EvidenceRecord`, which do carry RLS.
- **A missing `TenantControlStatus` row means `not_met`, not `null`/"unknown."** A tenant that has never
  touched a control is being measured against it as if it were failing, not exempted from measurement —
  matching how a real audit would treat an unassessed control. This is why the table is populated lazily
  rather than seeded per-tenant.
- **Evidence reuses `audit_logs`' polymorphic `target_type`/`target_id` shape rather than inventing a new
  one.** This is the same "reuse the established pattern" call Milestone 5 made explicitly for incident
  timelines and Milestone 6 made implicitly for correlation rules — a fourth distinct way to model
  "this record can point at one of several other entity types" would have been an unjustified new
  abstraction when one already existed and fit.
- **No file upload for evidence in this milestone.** The `object_storage_*` config settings have existed
  since Milestone 1 and were never wired to a client; building a real upload path here would have meant
  introducing and testing MinIO/S3 integration in an environment where Docker Compose itself is already
  flagged as unverified end-to-end (see Milestone 1's Known Limitations) — a structured, URL/note-based
  evidence record was the honest scope for this pass.

## Milestone 7 — Known Limitations

- **No file/document upload for evidence** — only titles, descriptions, URLs, and notes. Real document
  attachment (screenshots, signed PDFs, log exports) needs object storage wired up first; see the
  Architecture Decisions above.
- **Only a small, representative control subset is seeded** (5 controls per framework) — not a complete
  or certification-ready SOC 2/ISO 27001 control set. A tenant's real compliance program will always need
  more controls than this seed provides.
- **No tenant-configurable frameworks or controls** — the catalogue is fixed, code/seed-defined data
  (same as `asset_types`), not something a tenant can add to or customize. A tenant-authored custom
  framework is reasonable future work, not attempted here.
- **`trust_passport.manage` remains reserved and unused** — the permission matrix grants it to
  `security_administrator` and `compliance_manager`, and `MODULES` reserves a `trust_passport` key, but a
  public-facing shareable "trust passport" page is a distinct future deliverable from internal compliance
  tracking, not part of this milestone's scope.
- **No automatic linking between findings/incidents and compliance controls** — e.g. a critical finding
  never automatically marks a related control as `not_met`. All control status changes are manual.
- **No frontend automated tests were added for the new Compliance page or `EvidenceList` component** —
  same gap and rationale as every prior milestone's new pages: verified manually end-to-end via
  Playwright, passes lint/typecheck/build, but no dedicated Vitest coverage.

## Milestone 7 — Unresolved Risks

- Carried over from Milestones 1-6 (in-memory rate limiter, no second-approver support-access flow, no
  dependency/container/secret scanning in CI, Docker Compose still unverified end-to-end, the scoring
  formulas' simplicity, the inherent stakes of unattended action execution, the per-job resilience
  scoring weights) — none were touched this milestone and remain open.
- The evidence permission-per-target design (`TARGET_MANAGE_PERMISSION`) is a judgment call built to
  satisfy the permission matrix's existing internal consistency, not an explicit instruction — flagged
  for your review since it sets precedent for how any future evidence-attachable entity (e.g. a finding)
  would be gated.
- The control-scoring weights (met=1.0, partial=0.5, not_met=0.0, not_applicable excluded) are a judgment
  call, not derived from any stated specification — same category of flag as Milestone 6's per-job
  scoring weights.

## Milestone 7 — Pending Approvals

- This Milestone 7 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps are documented rather than hidden.
- Recommend explicit review of the evidence permission-per-target design and the control-scoring weights
  (see Architecture Decisions) — both are interpretations made in the absence of an explicit
  specification for this milestone.

---

## Milestone 8 — Completed Work

### Backend — `modules/reporting` (new, no models, no migration)
- **A pure composition module** — the smallest of any milestone so far. `get_executive_summary()` calls
  straight into the four summary functions every other module already built for its own dashboard tile
  (`findings.get_risk_summary`, `incidents.get_incident_summary`, `resilience.get_resilience_summary`,
  `compliance.get_compliance_summary`), plus one small `SELECT count(*)` over `assets`, and returns one
  combined bundle. No new table, no migration — like `modules.resilience`, there is nothing here for the
  module to own; it only synthesizes facts that already exist.
- **Route**: `GET /api/reports/executive-summary`, gated on `reports.view` alone — deliberately not
  re-checking `findings.view`/`incidents.view`/`compliance.view`/`assets.view` for each section it
  aggregates. `reports.view` is already granted to every one of the eight tenant roles in the permission
  matrix, including `executive_viewer`, who explicitly lacks `compliance.view` and `evidence.view`
  entirely — the only reading consistent with that is that `reports.view` is intentionally a
  cross-cutting synthesis permission for someone who needs the overall picture without day-to-day
  operational access to every module underneath it, not a permission that inherits each source's own
  gate. Every existing tenant role already holds it, so there was no role available to exercise a 403
  case for this endpoint — noted honestly in the test file rather than manufactured with a role that
  doesn't reflect the real matrix.

### Frontend (`apps/web`)
- New `/reports` page: one consolidated "Overall posture" card (security score, recovery confidence,
  compliance score), a 3-up row (assets, open findings by severity, open incidents by severity), and a
  compliance-frameworks breakdown — everything a viewer would otherwise have to visit four separate
  pages to piece together.
- **"Download JSON"** button: a client-side `Blob`/`URL.createObjectURL` download of the already-fetched
  summary, named `gridkeep-executive-summary-<date>.json`. No new backend export endpoint was needed —
  the data was already on the page.
- Dashboard gained a "View executive report →" link next to its header, gated on `reports.view`.
- Nav gained a "Reports" item, after Compliance.

## Milestone 8 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| Executive summary aggregates security score, incidents, resilience, and compliance correctly | ✅ | `test_executive_summary_aggregates_across_all_modules`; live-verified — after connecting a backup integration, setting a control to "met", and declaring a critical incident, the report showed security 70, recovery confidence 50, compliance 10, exactly matching the individual dashboard tiles |
| A tenant with no data gets sensible defaults, not errors | ✅ | `test_executive_summary_empty_tenant_has_sensible_defaults` — security 100, compliance 0 (frameworks are always seeded and scoreable), resilience `None` |
| The report is tenant-isolated | ✅ | `test_executive_summary_scoped_to_own_tenant` |
| `reports.view` is a genuine cross-cutting permission, not silently requiring each section's own view permission | ✅ | Verified by inspection of `DEFAULT_ROLE_PERMISSIONS` — every one of the 8 tenant roles holds `reports.view`, including `executive_viewer`, which lacks `compliance.view`/`evidence.view` outright |
| Downloading the report produces a well-formed, correctly-named JSON file | ✅ | Live-verified via a real Playwright download — `gridkeep-executive-summary-2026-07-16.json` containing the exact same figures shown on the page |
| No new migration was required | ✅ | `alembic current` unchanged — `modules/reporting` has no models |
| Backend tests pass | ✅ | **148/148** passing (`pytest -q` in `apps/api`, up from 144 — 4 new tests), plus **12/12** in `packages/connector-sdk` |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 22/22 routes |

## Milestone 8 — Test Results (as actually executed in this session)

```
packages/connector-sdk: pytest -q     → 12 passed
apps/api: pytest -q                   → 148 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 22/22 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Celery-worker/Next.js stack, driven by headless
Chromium, on a fresh tenant: opened `/reports` on an untouched tenant and confirmed the defaults (security
100, compliance 0/100 across both seeded frameworks, no assets/findings/incidents); connected the
`mock_backup` integration and synced it; set one SOC 2 control to "met"; declared a critical incident;
reopened `/reports` and confirmed every figure updated correctly and in agreement with the dashboard's
individual tiles (security 70, recovery confidence 50, compliance 10, 2 assets, 3 open findings — 2 High
+ 1 Medium, 1 open critical incident); clicked "Download JSON" and confirmed a real file downloaded with
the correct filename and matching data.

## Milestone 8 — Architecture Decisions (made or refined during implementation)

- **`reports.view` is deliberately treated as a standalone, cross-cutting permission**, not a proxy for
  "has view access to everything being summarized." This was the central judgment call of the milestone:
  the alternative (checking `findings.view` AND `incidents.view` AND `compliance.view` AND `assets.view`
  before including each section) would have silently hidden sections from `executive_viewer` — the one
  role whose entire purpose is consuming this exact report — since that role never held `compliance.view`
  or `evidence.view` to begin with. Treating `reports.view` as sufficient on its own is the only reading
  that makes the permission matrix's existing role design coherent.
- **No new export endpoint for the report** — unlike `evidence.export` (Milestone 7), which needed a
  dedicated route because the API is the only place with the target-scoped evidence query, the executive
  summary is a single already-fetched object; building a server-side export endpoint for data the client
  already has in memory would have been unjustified duplication. The download is a client-side `Blob`.
- **The module has zero models, deliberately** — this is the second milestone in a row (after
  Milestone 6's resilience module) to add real, tested functionality without touching the schema at all,
  by composing existing service functions rather than introducing a new table to cache or duplicate data
  that's already computable on demand.

## Milestone 8 — Known Limitations

- **No historical trend** — the executive summary is a point-in-time snapshot; there's no way to see how
  the security score, compliance score, or recovery confidence has moved over time. Same gap already
  noted for the individual security/compliance/resilience scores in Milestones 3, 6, and 7.
- **No PDF or formatted-document export** — only the client-side JSON download. A board-ready formatted
  document (with the company's branding, charts, etc.) is reasonable future work but would need a real
  document-generation dependency this codebase doesn't have yet.
- **No scheduled/emailed reports** — the summary is only available on-demand when a user visits the page;
  there's no periodic snapshot, subscription, or email digest.
- **No frontend automated tests were added for the new Reports page** — same gap and rationale as every
  prior milestone's new pages: verified manually end-to-end via Playwright, passes lint/typecheck/build,
  but no dedicated Vitest coverage.

## Milestone 8 — Unresolved Risks

- Carried over from Milestones 1-7 (in-memory rate limiter, no second-approver support-access flow, no
  dependency/container/secret scanning in CI, Docker Compose still unverified end-to-end, the scoring
  formulas' simplicity, the inherent stakes of unattended action execution, the evidence permission-per-
  target design, the control-scoring weights) — none were touched this milestone and remain open.
- The decision to gate the entire executive summary on `reports.view` alone, without per-section
  permission checks, is a judgment call flagged for your explicit review — it is the correct reading of
  the current permission matrix, but if a future role is added that holds `reports.view` without, say,
  `compliance.view`, that role would still see compliance data in this report. Worth confirming this is
  the intended semantics of `reports.view` going forward.

## Milestone 8 — Pending Approvals

- This Milestone 8 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps are documented rather than hidden.
- Recommend explicit review of the `reports.view` cross-cutting-permission decision (see Architecture
  Decisions and Unresolved Risks) — it's the interpretive core of this milestone and shapes how any
  future report-like surface should be gated.

---

## Milestone 9 — Completed Work

### Backend — `modules/trust_passport`
- **The last unused permission in the entire system.** Every permission in `PERMISSIONS` had a real
  route gating it by Milestone 8 except `trust_passport.manage` — flagged explicitly in Milestone 7's
  docs as "a distinct future deliverable from internal compliance tracking." This milestone builds it: a
  public, shareable "trust center" page a tenant can publish summarizing their security program, safe to
  send to a prospect or customer without giving them any access to GRIDKEEP itself.
- **`TrustPassportSettings`**: one row per tenant (same lazy-singleton shape as Milestone 4's
  `TenantAutomationSetting` — absence of a row means "never configured"), holding `is_published`,
  `public_slug`, `headline`, `description`, `show_compliance_frameworks`. `public_slug` is stored in
  **plaintext**, deliberately unlike session or invitation tokens — those are secrets that grant a
  privileged action if leaked, so they're hashed at rest; this slug *is* the public identifier, designed
  to be shared and put in a URL, so there is nothing to protect by hashing it.
- **The first unauthenticated, data-returning endpoint in this codebase.** `GET /api/public/trust-
  passport/{slug}` takes no session cookie and resolves no `TenantContext` at all. Making this safe
  required a genuine new RLS pattern: rather than the standard `_SIMPLE_TENANT_TABLES` shape, the
  `trust_passport_settings` table's SELECT policy is widened — mirroring the exact precedent Milestone 1
  already set for `memberships` (`FOR SELECT ... USING (tenant_id = app_current_tenant_id() OR ...)`) —
  to `tenant_id = app_current_tenant_id() OR is_published = true`. An anonymous session (where
  `app_current_tenant_id()` is `NULL`) can therefore only ever see rows that are explicitly published;
  INSERT/UPDATE/DELETE remain strictly tenant-scoped with no widening at all, so publishing or editing a
  passport always requires being authenticated into that exact tenant. Once the public route finds a
  published row, it calls `set_tenant_context` with that row's own `tenant_id` — the same mechanism
  `get_tenant_context` uses after resolving a tenant from a session cookie, just resolved from a slug
  instead — so every subsequent query in that request is normally tenant-scoped, not broadened.
- **Coarse labels only, never raw scores, on the public page.** `get_public_passport()` reuses
  `compliance_service.get_compliance_summary()` exactly like Milestone 8's executive summary did, but
  converts each framework's numeric score to one of three labels (`Strong` / `In Progress` / `Building`)
  before it ever leaves the service layer — a public page showing "38% compliant" reads as an admission
  of failure to an outside visitor in a way "In Progress" doesn't; the real number stays behind
  `compliance.view` on the internal `/compliance` page.
- **Slug lifecycle**: a slug is generated automatically the first time a tenant publishes (no slug
  needed for a draft/never-published passport); unpublishing does *not* clear the slug, so republishing
  reuses the same URL rather than silently breaking a link someone may have already been given;
  `POST /api/trust-passport/settings/regenerate-slug` lets a tenant explicitly rotate the link (e.g. if
  it leaked somewhere it shouldn't have) — the old slug stops resolving immediately.
- **Routes**: `GET/PATCH /api/trust-passport/settings` and `POST .../regenerate-slug`, all gated on
  `trust_passport.manage` alone (there is no separate `trust_passport.view` — same "one manage permission,
  no view permission" shape Milestone 4 used for `automations.manage`).

### Frontend (`apps/web`)
- New `/settings/trust-passport` page: status card (published/draft, the public URL with copy/regenerate
  actions), content card (headline, description, show-compliance-frameworks toggle, publish/unpublish).
- New **top-level** `apps/web/app/trust/[slug]/page.tsx` — deliberately outside both the `(auth)` and
  `(tenant)` route groups, so it renders with no `AppShell`, no nav, and no dependency on the
  authenticated `useAuth()` context at all; it fetches directly from the public API endpoint.
- Nav gained a "Trust Passport" item under Settings.

## Milestone 9 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| A tenant can configure and publish a trust passport | ✅ | `test_update_settings_generates_slug_on_first_publish`; live-verified via the settings UI |
| A slug is generated only on first publish, and stays stable across further edits | ✅ | `test_update_settings_does_not_regenerate_slug_on_subsequent_updates` |
| Unpublishing hides the page but keeps the slug for republishing | ✅ | `test_unpublishing_keeps_the_slug_but_hides_the_page` |
| Regenerating the slug invalidates the old URL immediately | ✅ | `test_regenerate_slug_changes_it_and_invalidates_the_old_one`; live-verified — the old link returned "Not found" in a real anonymous browser context immediately after regenerating |
| The public page is reachable with **zero cookies**, not just "logged out in the same tab" | ✅ | Live-verified with a fresh Playwright browser context carrying no cookies at all for the API origin (`anon_context.cookies(...)` confirmed empty) |
| The public page never exposes a raw compliance score, only a coarse label | ✅ | `test_public_passport_shows_coarse_labels_not_raw_scores` (asserts `"score" not in` the returned entry); live-verified — both frameworks showed "Building," never a number |
| An unpublished or nonexistent slug returns 404, not the settings | ✅ | `test_get_public_passport_wrong_slug_raises_not_found`, `test_public_passport_404_for_unpublished_slug` |
| A role without `trust_passport.manage` cannot configure the passport | ✅ | `test_security_analyst_cannot_manage_trust_passport` |
| `show_compliance_frameworks` is respected on the public page | ✅ | `test_public_passport_respects_show_compliance_frameworks_toggle` |
| Backend tests pass | ✅ | **160/160** passing (`pytest -q` in `apps/api`, up from 148 — 12 new tests), plus **12/12** in `packages/connector-sdk` |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 23/23 routes |

## Milestone 9 — Test Results (as actually executed in this session)

```
packages/connector-sdk: pytest -q     → 12 passed
apps/api: pytest -q                   → 160 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 23/23 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Celery-worker/Next.js stack, driven by headless
Chromium, using **two separate browser contexts** (one authenticated, one carrying zero cookies) rather
than one browser reused: onboarded a fresh tenant, opened `/settings/trust-passport`, set a headline and
description, and published — a real public slug appeared immediately; navigated to that exact URL in the
cookie-free context and confirmed the public page rendered with no nav/AppShell, the tenant's own
headline/description, and both compliance frameworks correctly labeled "Building" (neither had any met
controls); clicked "Regenerate link" in the authenticated context and confirmed the settings page showed
a new, different slug; re-navigated the cookie-free context to the *old* URL and confirmed it now returns
"Not found" rather than the passport.

## Milestone 9 — Architecture Decisions (made or refined during implementation)

- **The public endpoint resolves its tenant from the row it finds, then narrows the rest of the request
  to it.** This was the central design problem of the milestone: an anonymous request has no tenant to
  scope by in advance. Widening the RLS SELECT policy (mirroring `memberships`) answers "which tenant
  does this slug belong to," and `set_tenant_context` immediately after answers "now restrict everything
  else in this request to exactly that tenant" — the same two-step shape `get_tenant_context` already
  uses for cookie-authenticated requests, just with a different first step.
- **Coarse public labels, computed once, in the service layer — not left to the frontend.** The label
  bucketing (`_status_label`) happens in `modules.trust_passport.service`, so `PublicTrustPassportRead`
  structurally cannot carry a raw score; a frontend bug can't accidentally leak one, because the number
  never crosses the API boundary in the first place.
- **The slug is plaintext at rest, and this is a deliberate departure from every other token in this
  codebase**, not an oversight — session tokens, invitation tokens, and password-reset tokens are all
  hashed because possessing the plaintext grants a privileged action. Possessing this slug grants
  exactly the ability the tenant explicitly wants to grant: viewing the public page. Hashing it would
  only add cost with no security benefit.
- **Unpublishing doesn't clear the slug.** The alternative — wiping `public_slug` back to `null` on
  unpublish — would silently invalidate a URL the tenant may have already handed to a customer, the first
  time they toggle the page off for any reason (even briefly). Keeping the slug stable and gating
  visibility purely on `is_published` means "take the page down temporarily" and "burn this link forever"
  are two different, deliberately separate actions (the latter is what "regenerate" is for).

## Milestone 9 — Known Limitations

- **Only compliance framework status is shown on the public page** — no security score, no incident
  history, no asset counts. This is a deliberate initial scope (the most reputation-sensitive, most
  already-external-facing category), not a technical ceiling; a future milestone could add opt-in
  sections for other summaries the same way `show_compliance_frameworks` works today.
- **No per-framework selection** — `show_compliance_frameworks` is all-or-nothing across every seeded
  framework; a tenant can't publish just their SOC 2 status while hiding ISO 27001. Reasonable future
  work, not attempted here to keep this milestone's scope coherent.
- **No custom branding/theming** on the public page — it's a plain GRIDKEEP-styled page, not a
  white-labeled one matching the tenant's own brand.
- **No analytics on the public page** — a tenant can't see how many times their trust passport has been
  viewed, or by whom.
- **No frontend automated tests were added for the new settings page or the public passport page** —
  same gap and rationale as every prior milestone's new pages: verified manually end-to-end via
  Playwright (including with a genuinely cookie-free browser context), passes lint/typecheck/build, but
  no dedicated Vitest coverage.

## Milestone 9 — Unresolved Risks

- Carried over from Milestones 1-8 (in-memory rate limiter, no second-approver support-access flow, no
  dependency/container/secret scanning in CI, Docker Compose still unverified end-to-end, the scoring
  formulas' simplicity, the inherent stakes of unattended action execution, the evidence permission-per-
  target design, the control-scoring weights, the `reports.view` cross-cutting-permission decision) —
  none were touched this milestone and remain open.
- This is the first RLS policy in the codebase that widens SELECT based on a *data value*
  (`is_published`) rather than an *identity* claim (`memberships`' `user_id = app_current_user_id()`).
  It's the correct and narrowly-scoped precedent for "a tenant explicitly opts a specific row into public
  visibility," but it's a new category of policy worth your explicit review before it becomes a template
  for a different future public-data feature.
- The status-label thresholds (`>=80` Strong, `>=50` In Progress, else Building) are a judgment call, not
  derived from any stated specification — same category of flag as the scoring weights in Milestones 6
  and 7.

## Milestone 9 — Pending Approvals

- This Milestone 9 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps are documented rather than hidden.
- Recommend explicit review of the widened-RLS-by-data-value pattern (see Architecture Decisions and
  Unresolved Risks) specifically — it's the first policy of its kind in the codebase and sets precedent
  for any future publicly-shareable data.

---

## Milestone 10 — Completed Work

### Backend — `modules/threat_intel`
- **The "different subsystem" this codebase has been pointing at since Milestone 2.** Both
  `modules.assets.ingestion`'s `RECORD_TYPE_TO_ASSET_TYPE_KEY` docstring and the `mock_threat_intel`
  connector's own docstring have said all along that `threat_intel.indicator` records are deliberately
  skipped by asset ingestion because "that data belongs to a different subsystem" — this milestone builds
  it. Every other permission in the system was already wired to a route by Milestone 9, so this one came
  from an explicit in-repo breadcrumb instead of the permission matrix.
- **`ThreatIndicator`**: a new tenant-scoped table, deliberately *not* an `Asset` — an indicator of
  compromise describes an external threat, not infrastructure the tenant owns. `indicator_type` is a free
  string, not a Postgres enum, since a real threat-intel feed's vocabulary (ip, domain, hash, url, ...) is
  open-ended and connector-defined — the same reasoning `AssetType.category` already used. Ordinary RLS
  (`_SIMPLE_TENANT_TABLES` shape) — no widened-SELECT pattern needed here, unlike Milestone 9's trust
  passport.
- **`modules.threat_intel.ingestion.ingest_threat_indicators()`**: filters `threat_intel.indicator`
  records out of the same connector record stream `ingest_sync_records` already consumes, upserting by
  `(tenant_id, external_id)`. Deliberately simpler than asset ingestion — no relationship graph, no
  change-log table, since a refined confidence/timestamp isn't evidence-worthy the way an asset attribute
  changing is.
- **`modules.threat_intel.engine.run_threat_intel_correlation()`**: a genuinely different detection shape
  from `modules.findings.engine.run_correlation` — it cross-references every stored indicator's value
  against every asset's own `attributes` dict (case-insensitive match on any attribute value, not one
  fixed key), rather than evaluating one asset's attributes against a fixed per-asset-type rule. This is
  why it stays a separate engine instead of a new entry in `modules.findings.rules.RULES` — but it writes
  into the exact same `Finding` table, and reuses the identical create/update/reopen/auto-resolve
  lifecycle `run_correlation` established in Milestone 3. Severity is derived from the indicator's own
  confidence (`>=0.7` critical, `>=0.4` high, else medium) — a live match against a known threat is
  treated as more serious than a static misconfiguration finding, since the asset actually communicated
  with (or otherwise matched) something on a threat feed, not just a theoretical weakness.
- **Demo scenario**: `mock_endpoint`'s already-flagged stale, EDR-unresponsive `sales-laptop-11` gained a
  `last_known_public_ip` attribute matching `mock_threat_intel`'s `mock-ioc-001` — a realistic
  convergence of independent risk signals (stale check-in + unresponsive EDR + a known-malicious IP)
  landing on one asset, live-verified to produce three simultaneous findings.
- **Worker**: `_run_integration_sync_async` now also calls `ingest_threat_indicators` on every sync
  (harmless no-op for connectors that don't produce indicators), and chains a new
  `enqueue_run_threat_intel_correlation` alongside the existing `enqueue_run_correlation` — every sync
  re-evaluates both directions, since a new indicator can match an existing asset just as easily as a new
  asset can match an existing indicator.
- **Route**: `GET /api/threat-intel/indicators`, gated on `findings.view` — chosen because indicators
  exist purely to feed the findings pipeline; the permission for viewing findings is the natural fit for
  viewing the raw indicator data behind the threat-intel-sourced ones. As with Milestone 8's `reports.view`
  decision, every tenant role already holds `findings.view`, so there was no role available to exercise a
  403 case for this endpoint either — noted honestly rather than fabricated.

### Frontend (`apps/web`)
- New `/threat-intel` page: every stored indicator (value, type, confidence, source, last seen) and which
  assets it matched, linking straight through to the resulting finding.
- Nav gained a "Threat Intel" item, after Findings.

## Milestone 10 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| Threat-intel indicators are ingested into their own table, not the asset graph | ✅ | `test_ingest_threat_indicators_creates_then_updates` |
| An asset attribute matching a known indicator creates a finding automatically | ✅ | `test_correlation_flags_endpoint_matching_known_indicator`; live-verified — `sales-laptop-11`'s planted IP produced a Critical "Asset matched a known threat indicator (ip)" finding |
| Finding severity is derived from the indicator's confidence | ✅ | Same test asserts `severity == "critical"` for confidence 0.8 |
| Re-running correlation on unchanged data is a no-op beyond refreshed timestamps | ✅ | `test_correlation_is_idempotent_on_rerun` |
| A finding auto-resolves when its indicator no longer matches any asset | ✅ | `test_correlation_auto_resolves_when_indicator_value_changes` |
| The indicators endpoint shows match status per indicator | ✅ | `test_indicators_endpoint_lists_matches`; live-verified — the domain indicator correctly showed "No matches" |
| Indicators are tenant-isolated | ✅ | `test_indicators_scoped_to_own_tenant` |
| A single asset can carry multiple simultaneous findings from independent engines | ✅ | Live-verified — `sales-laptop-11` showed three open findings at once: the new IOC match plus its pre-existing `edr_agent_unresponsive` and `stale_device_checkin` |
| No regression to the asset-correlation pipeline from the added worker step | ✅ | Full backend suite passes; `run_correlation` and `run_threat_intel_correlation` both fire independently after every sync (confirmed in live worker logs) |
| Backend tests pass | ✅ | **166/166** passing (`pytest -q` in `apps/api`, up from 160 — 6 new tests), plus **12/12** in `packages/connector-sdk` |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 24/24 routes |

## Milestone 10 — Test Results (as actually executed in this session)

```
packages/connector-sdk: pytest -q     → 12 passed
apps/api: pytest -q                   → 166 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 24/24 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Celery-worker/Next.js stack, driven by headless
Chromium, on a fresh tenant: connected the Simulated Endpoint Platform and synced it; connected the
Simulated Threat Intelligence Feed and synced it; confirmed the worker log showed both
`run_correlation` and `run_threat_intel_correlation` firing after each sync; opened `/threat-intel` and
confirmed the IP indicator showed `sales-laptop-11.example-tenant.local` as a match (a live link straight
to the resulting finding) while the domain indicator correctly showed "No matches"; opened `/findings`
and confirmed `sales-laptop-11` carried three simultaneous open findings — the new Critical "Asset
matched a known threat indicator (ip)" alongside its pre-existing High "EDR agent unresponsive" and
Medium "Device has not checked in recently."

## Milestone 10 — Architecture Decisions (made or refined during implementation)

- **Threat-intel correlation is a separate engine from `modules.findings.engine`, not a new rule in the
  existing registry.** `modules.findings.rules.RULES` evaluates one asset's own attributes against a
  fixed condition — that shape doesn't fit "does this external indicator show up anywhere in what we
  discovered," which requires cross-referencing two collections. Keeping them separate engines (both
  writing into the same `Finding` table with the same lifecycle semantics) avoided distorting the
  existing rule registry's shape to fit a problem it wasn't designed for.
- **Matching is attribute-value-agnostic, not keyed to one fixed field like `ip_address`.** Checking
  every attribute value on an asset (case-insensitively) against every indicator value means this keeps
  working regardless of what shape any current or future connector's attributes happen to take, without a
  schema or matching-logic change here — the tradeoff is O(indicators × assets × attributes) rather than
  an indexed lookup, acceptable at the scale a single tenant's asset graph actually reaches.
- **No change-log table for indicators, unlike assets.** `AssetChange` exists because an asset's
  attribute history has evidentiary value (M2's architecture reasoning); an indicator's confidence being
  refreshed on every re-sync doesn't carry the same weight — it's external threat-feed data being kept
  current, not a fact about the tenant's own infrastructure changing over time.
- **`findings.view` gates the indicators endpoint**, following the exact reasoning Milestone 8 used for
  `reports.view`: pick the permission that already governs the pipeline this data feeds, rather than
  inventing a new one for a small, tightly-scoped piece of data with no natural permission of its own.

## Milestone 10 — Known Limitations

- **Threat-intel matches don't yet trigger playbook automation** the way asset-correlation findings do
  (Milestone 4) — `run_threat_intel_correlation`'s summary doesn't track `actionable_finding_ids` the way
  `run_correlation`'s does. A reasonable future integration between the two engines, not attempted here
  to keep this milestone's scope coherent.
- **Sync-run reporting (`IntegrationSyncRun.records_processed/created/updated`) still reflects asset
  ingestion only** — threat-intel ingestion counts aren't surfaced there, only via the indicators list
  page itself. Adding indicator counts to that schema was out of scope for this pass.
- **Matching is exact-value, case-insensitive only** — no CIDR-range matching for IPs, no subdomain
  matching for domains, no fuzzy/partial matching. A real threat-intel integration would likely need
  richer matching semantics; this is the honest, simple baseline.
- **Only one connector (`mock_threat_intel`) produces indicators today** — the ingestion and correlation
  pipeline works against any connector emitting `threat_intel.indicator` records with the same shape, but
  only the mock one exists; a real threat-intel feed integration is future work.
- **No frontend automated tests were added for the new Threat Intel page** — same gap and rationale as
  every prior milestone's new pages: verified manually end-to-end via Playwright, passes
  lint/typecheck/build, but no dedicated Vitest coverage.

## Milestone 10 — Unresolved Risks

- Carried over from Milestones 1-9 (in-memory rate limiter, no second-approver support-access flow, no
  dependency/container/secret scanning in CI, Docker Compose still unverified end-to-end, the scoring
  formulas' simplicity, the inherent stakes of unattended action execution, the evidence permission-per-
  target design, the control-scoring weights, the `reports.view` cross-cutting-permission decision, the
  widened-RLS-by-data-value pattern) — none were touched this milestone and remain open.
- The confidence-to-severity thresholds (`>=0.7` critical, `>=0.4` high, else medium) are a judgment
  call, not derived from any stated specification — same category of flag as the resilience/compliance
  scoring weights in Milestones 6-7.
- The O(indicators × assets × attributes) matching approach is a deliberate simplicity-over-scale
  tradeoff, flagged for your review since a tenant with a very large asset graph and many indicators would
  eventually want an indexed lookup instead.

## Milestone 10 — Pending Approvals

- This Milestone 10 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps are documented rather than hidden.
- Recommend explicit review of the confidence-to-severity thresholds and the attribute-matching approach
  (see Architecture Decisions and Unresolved Risks) — both are interpretations made in the absence of an
  explicit specification for this milestone.

## Milestone 10 — Next Action

Milestone 10 was approved and Milestone 11 is complete — see below.

## Milestone 11 — Completed Work

### Backend — `modules/attack_surface` (new module; operates on `modules.tenancy.models.TenantDomain`)

- **The breadcrumb this milestone came from.** By Milestone 9 every `PERMISSIONS` entry in
  `security-contracts` was already wired to a real route, so the usual scope signal was exhausted (as it
  was for Milestone 10). `TenantDomain` has existed since Milestone 1 as schema-only — no service, no
  routes — with its own docstring naming "Verification mechanics (DNS TXT / email)" as unbuilt future
  work. This milestone builds that: real domain ownership verification, the last dormant table in the
  schema.
- **Mechanism substitution, made explicit in `TenantDomain`'s docstring**: verification is **HTTP-file**
  based (`GET https://{domain}/.well-known/gridkeep-verification.txt` must contain the record's
  `verification_token`) rather than the DNS TXT lookup the docstring originally named. Raw DNS queries
  (tested directly with `dnspython`, including against the sandbox's own configured nameserver) time out
  in the environment this was built in — network-blocked, not a code bug. Rather than ship
  untestable/broken DNS code, or worse, fake a "verified" result the way a mock connector is allowed to
  fake demo *data*, the mechanism was substituted for one that performs a genuine outbound check and can
  actually be built and tested here. DNS TXT and email verification remain reasonable future methods.
- **`verification_token`**: new nullable column on the existing `tenant_domains` table (additive
  migration), generated via the same `core.security.generate_opaque_token` used for Milestone 9's trust
  passport `public_slug` — stored plaintext, not hashed, since it's meant to be published by the tenant,
  not kept secret.
- **`modules.attack_surface.service`**: `add_domain` (normalizes to lowercase, generates a token, and
  rejects a same-tenant duplicate via an RLS-visible pre-check); `list_domains`; `remove_domain`;
  `verify_domain` (makes a real `httpx.AsyncClient` GET against the domain's well-known path — the first
  non-test app code in the repo to make a genuine outbound HTTP call — and flips `is_verified` only if the
  response is HTTP 200 and its body contains the stored token). `scheme` defaults to `"https"` and is
  never exposed as a client-controllable parameter on the route; only tests override it to hit a local
  server over plain HTTP.
- **Cross-tenant uniqueness discovery**: `tenant_domains` has RLS restricting `SELECT` to the caller's own
  tenant (it's in the `_SIMPLE_TENANT_TABLES` list, unlike Milestone 1's `memberships` widened-SELECT
  exception). That means `add_domain`'s pre-check can only ever see a same-tenant duplicate — a domain
  already claimed by a *different* tenant is invisible to that `SELECT` and only surfaces as an
  `IntegrityError` against the table's pre-existing global `UniqueConstraint("domain")` when the insert
  runs. `add_domain` catches that specific case and turns it into the same `ConflictError` (409) a caller
  would expect, rather than leaking a raw database error. This is a genuine consequence of the RLS design
  established in Milestone 1, not a new limitation introduced here.
- **Routes**: `GET /api/attack-surface/domains` (`assets.view`); `POST /api/attack-surface/domains`,
  `POST /api/attack-surface/domains/{id}/verify`, `DELETE /api/attack-surface/domains/{id}` (all
  `assets.manage`) — domains are part of the discoverable attack-surface/asset inventory, so the existing
  asset permissions were the natural fit rather than inventing new ones, following the same reasoning
  Milestone 6 used for `modules.resilience` operating on `modules.assets.models.Asset` without owning it.

### Frontend (`apps/web`)
- New `/attack-surface` page: add a domain, see its verification instructions (well-known URL + token) if
  unverified, trigger a real verification check, remove a domain.
- Nav gained an "Attack Surface" item, after Assets.

## Milestone 11 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| Adding a domain generates a verification token | ✅ | `test_add_domain_generates_a_verification_token` |
| A domain already added by the same tenant is rejected as a conflict | ✅ | `test_add_domain_twice_for_same_tenant_conflicts` |
| A domain already claimed by a different tenant is rejected as a conflict, not a raw DB error | ✅ | `test_add_domain_already_claimed_by_another_tenant_conflicts` |
| Domains are tenant-isolated in listings | ✅ | `test_list_domains_only_returns_the_tenant_own_domains` |
| Verification succeeds only when a real HTTP fetch finds the token in the response body | ✅ | `test_verify_domain_succeeds_when_token_is_present` — against a genuine local HTTP server, not a mock |
| Verification correctly fails on a wrong token, an unreachable host, and a non-200 response | ✅ | `test_verify_domain_fails_when_token_is_wrong`, `test_verify_domain_fails_when_host_is_unreachable`, `test_verify_domain_fails_when_status_is_not_200` |
| A domain can be removed | ✅ | `test_remove_domain`; live-verified via the UI |
| `assets.manage` gates add/verify/remove; `assets.view` gates listing | ✅ | `test_security_analyst_can_view_but_not_manage_domains` — a `security_analyst` (has `assets.view`, not `assets.manage`) gets 200 on list, 403 on add |
| Full API flow (add → list → remove) works end-to-end over HTTP | ✅ | `test_api_add_list_and_remove_domain` |
| Backend tests pass | ✅ | **180/180** passing (`pytest -q` in `apps/api`, up from 166 — 14 new tests), plus **12/12** in `packages/connector-sdk` |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 26/26 routes |

## Milestone 11 — Test Results (as actually executed in this session)

```
packages/connector-sdk: pytest -q     → 12 passed
apps/api: pytest -q                   → 180 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 26/26 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Next.js stack, driven by headless Chromium: logged in
as the demo tenant owner, opened `/attack-surface`, added a domain, confirmed the "Unverified" badge and
the well-known URL/token instructions rendered, clicked "Verify now" and confirmed a **real** outbound
HTTP request was attempted (visible in the UI as "Could not reach ... " for the deliberately-unreachable
test domain used), confirmed the domain correctly remained Unverified, then removed it and confirmed it
disappeared from the list. The success path (a real HTTP 200 response containing the token) is covered by
the backend test suite against a genuine local HTTP server rather than the browser flow — see Known
Limitations below for why.

## Milestone 11 — Architecture Decisions (made or refined during implementation)

- **HTTP-file verification instead of DNS TXT**, detailed above and in `TenantDomain`'s docstring — a
  substitution made for environment feasibility, preserving the feature's actual security purpose (a real
  check) rather than either shipping untestable code or faking the result.
- **`scheme` is a service-layer parameter, not client-controllable.** `verify_domain(..., scheme="https")`
  exists so tests can point at a local HTTP server, but the route never accepts or forwards a
  client-supplied scheme — a real ownership check has to run over HTTPS, and letting a caller downgrade
  that would defeat the point of the control.
- **The cross-tenant conflict is caught via `IntegrityError`, not a second cross-tenant SELECT.** Bypassing
  RLS to check "does any other tenant already have this domain" would need a privileged query path that
  doesn't otherwise exist in this codebase; catching the database's own global uniqueness constraint at
  insert time is simpler, already-enforced-by-the-schema, and doesn't require inventing a new
  RLS-bypass mechanism for one check.
- **`assets.view`/`assets.manage` gate this module**, following the exact precedent Milestone 6 set for
  `modules.resilience` and Milestone 8 for `modules.reporting`: a module doesn't need to own the model it
  operates on, and an existing permission that already fits is preferable to a new one.

## Milestone 11 — Known Limitations

- **The verification-success path was not exercised through the live browser E2E flow.** Making a real
  outbound HTTPS request that succeeds requires a domain the tester actually controls the content of —
  not available in this sandboxed environment. The success path (HTTP 200, token present) is genuinely
  exercised, but by the backend test suite against a real local HTTP server over plain HTTP
  (`test_verify_domain_succeeds_when_token_is_present`), not by the UI. The failure paths (wrong token,
  unreachable host, non-200) are exercised at both layers, including live through the browser.
- **DNS TXT and email verification remain unbuilt**, as originally scoped in `TenantDomain`'s Milestone 1
  docstring — only HTTP-file verification exists. A reasonable follow-up, not attempted here since one
  working, real mechanism was judged more valuable than three partially-stubbed ones.
- **No rate limiting or retry/backoff on the verification HTTP request itself** beyond the existing global
  rate limiter on the route — a tenant could hammer `/verify` against a slow-to-respond host. The 10-second
  request timeout bounds the damage per call but repeated calls aren't throttled specifically.
- **No frontend automated tests were added for the new Attack Surface page** — same gap and rationale as
  every prior milestone's new pages: verified manually end-to-end via Playwright, passes
  lint/typecheck/build, but no dedicated Vitest coverage.

## Milestone 11 — Unresolved Risks

- Carried over from Milestones 1-10 (in-memory rate limiter, no second-approver support-access flow, no
  dependency/container/secret scanning in CI, Docker Compose still unverified end-to-end, the scoring
  formulas' simplicity, the inherent stakes of unattended action execution, the evidence
  permission-per-target design, the control-scoring weights, the `reports.view`/`findings.view`
  cross-cutting-permission decisions, the widened-RLS-by-data-value pattern, the threat-intel
  confidence-to-severity thresholds and O(n×m) matching approach) — none were touched this milestone and
  remain open.
- The HTTP-file verification mechanism itself is a substitution for the originally-scoped DNS TXT
  approach, made for this environment's network constraints — flagged for explicit review since it's a
  deviation from what the dormant schema's own docstring had named, even though it preserves the same
  security property (genuine, checkable proof of domain control).
- A tenant that loses control of a previously-verified domain (e.g., it expires and is re-registered by
  someone else) stays marked `is_verified=True` indefinitely — there's no re-verification/expiry policy.
  Reasonable future work, out of scope here.

## Milestone 11 — Pending Approvals

- This Milestone 11 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps are documented rather than hidden.
- Recommend explicit review of the DNS-TXT-to-HTTP-file mechanism substitution (see Architecture Decisions
  and Unresolved Risks) — this is a deviation from what the pre-existing schema's docstring specified,
  made for environment feasibility rather than because it was asked for.

## Milestone 11 — Next Action

Milestone 11 was approved and Milestone 12 is complete — see below.

## Milestone 12 — Completed Work

### The breadcrumb this milestone came from
- By Milestone 9 every tenant-facing `PERMISSIONS` entry was wired to a route, so the usual scope signal
  was exhausted again (as it was for Milestones 10 and 11). A dedicated research pass found something the
  earlier "every permission is wired" claim had actually missed: two **platform** permissions —
  `platform.tenants.manage` and `platform.audit.view` — have existed since Milestone 1 with a role
  (`platform_auditor`) that exists for no other purpose than holding the latter, yet neither was ever
  wired to a route. The enforcement machinery both permissions imply was already fully built and idle:
  `TENANT_STATUSES`/`WRITE_BLOCKED_STATUSES` gate every tenant write, and `audit_service.record()` is
  called from 50+ call sites across nearly every module, but nothing could ever change a tenant's status
  or view the audit trail it was already writing. This milestone builds both.
- A related, more foundational gap surfaced while scoping this: `UserRead`/`LoginResponse`/`MeResponse`
  never exposed `is_platform_user` at all, even though platform users already log in through the exact
  same `/api/auth/login` endpoint tenant users do (confirmed by Milestone 1's own
  `test_platform_admin_can_grant_and_revoke_support_access` test). The frontend had no way to know a
  logged-in user was a platform admin, and the post-login redirect logic would have sent a
  zero-membership platform user into a `/select-workspace` redirect loop. That plumbing gap had to be
  closed before any platform-facing UI could exist at all.

### Backend
- **`UserRead`** (`modules/identity/schemas.py`) gained `is_platform_user: bool` and
  `platform_role_name: str | None`. `platform_role_id` is a bare FK (kept structurally separate from
  tenant roles per the platform-roles-stay-separated rule), so a new `identity_service.get_platform_role_name()`
  resolves the name with its own query rather than a relationship traversal; `_build_user_read()` composes
  it at `login` and `/me`.
- **`packages/security-contracts`**: added `DEFAULT_PLATFORM_ROLE_PERMISSIONS` to the TypeScript side,
  mirroring the Python dict that already existed — the same client-side-permission-mapping pattern
  Milestone 1 established for tenant roles (`DEFAULT_ROLE_PERMISSIONS`), just never extended to platform
  roles. A new sync test (`test_platform_role_permissions_match`) guards it the same way the existing enum
  sync tests do.
- **Widened `audit_logs_select` RLS policy** (new migration): the existing policy only let a
  platform-admin session see `tenant_id IS NULL` rows (platform-level events like login/logout) — it never
  actually granted cross-tenant visibility into ordinary tenant-scoped audit rows, despite
  `app_is_platform_admin()` existing since Milestone 1's very first RLS migration seemingly for that
  purpose. Widened to `tenant_id = app_current_tenant_id() OR app_is_platform_admin()`, following the same
  widened-SELECT precedent as Milestone 1's `memberships` and Milestone 9's `trust_passport_settings`.
- **`db.session.platform_admin_scoped_session()`** (new): sets `app.is_platform_admin=true` with no single
  tenant selected, so the widened policy's OR clause is unconditionally true for that session — the one
  session flavour that should ever see more than one tenant's audit history at once. `core.deps.get_platform_admin_db`
  wires it as a route dependency, composing with `require_platform_permission` exactly the way
  `get_tenant_db` composes with `require_permission`.
- **`modules.platform_admin.service`**: `list_tenants`/`get_tenant_or_404` (the `tenants` table carries no
  RLS of its own — it's the tenancy root, not a tenant-owned row — so a plain session already sees every
  tenant); `update_tenant_status`, validated against an explicit state machine
  (`_VALID_TENANT_STATUS_TRANSITIONS`) where `archived` is terminal and every other status can reach
  `suspended`/`archived` or `active`. Reuses Milestone 1's `set_tenant_context(..., is_platform_admin=True)`
  session-variable pattern (the same one `create_grant`/`revoke_grant` already used) so the
  `audit_logs_insert` policy is satisfied when the status-change audit record is written.
- **`modules.audit.service.list_platform_wide()`**: the actual cross-tenant audit query, filterable by
  `tenant_id`/`action`, paginated. Belongs in `audit`, not `platform_admin`, since audit-log querying is
  audit's job — the same "a module doesn't need to own the model it operates on" reasoning Milestones 6/8/11
  already established, just applied to a service function instead of a whole module.
- **Routes** (`modules/platform_admin/routes.py`): `GET /api/platform/tenants`,
  `GET /api/platform/tenants/{id}`, `POST /api/platform/tenants/{id}/status` (all `platform.tenants.manage`);
  `GET /api/platform/audit-logs` (`platform.audit.view`, the only route using `get_platform_admin_db`).

### Frontend (`apps/web`)
- New `app/platform/` route (a real folder, not a route group — `(platform)` would not have added a URL
  prefix, the same way `(tenant)` and `(auth)` don't; this was caught and fixed during build verification,
  not left as a latent bug).
- `PlatformShell` component + `platform/layout.tsx` guarding on `isPlatformUser`, mirroring the tenant
  `AppShell`/`(tenant)/layout.tsx` pattern but with no membership dependency.
- `/platform/tenants`: every tenant on the platform, with an inline status-change form (new status +
  required reason, audit-logged).
- `/platform/audit-logs`: the platform-wide audit trail, filterable by tenant and action.
- Login now redirects a platform user straight to `/platform` instead of `/dashboard`/`/select-workspace`.
- `useAuth()` gained `isPlatformUser`/`platformPermissions`/`hasPlatformPermission`, computed client-side
  from `platform_role_name` via `DEFAULT_PLATFORM_ROLE_PERMISSIONS` — identical in shape to how tenant
  permissions are already computed from `role_name`.

## Milestone 12 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| A platform user's login/`/me` response identifies them as a platform user and names their role | ✅ | `test_login_response_exposes_platform_role_for_a_platform_user`, `test_login_response_shows_is_platform_user_false_for_a_tenant_user` |
| `DEFAULT_PLATFORM_ROLE_PERMISSIONS` stays in sync between Python and TypeScript | ✅ | `test_platform_role_permissions_match` |
| A platform admin can list every tenant and view one tenant's detail | ✅ | `test_platform_admin_can_list_and_view_tenants`; live-verified — the seeded demo tenant appeared in the list |
| A tenant's status can be changed along valid transitions only | ✅ | `test_platform_admin_can_transition_tenant_status`, `test_invalid_tenant_status_transition_is_rejected`, `test_archived_tenant_status_is_terminal` |
| Every status change is audit-logged with actor, reason, and from/to | ✅ | `test_tenant_status_change_is_audit_logged_and_visible_platform_wide` |
| A platform admin can view audit events across every tenant, not just their own | ✅ | `test_platform_wide_audit_log_shows_entries_from_multiple_tenants` — the test that actually exercises the widened RLS policy, not just the application code on top of it; live-verified via the UI |
| `platform.tenants.manage` and `platform.audit.view` are independently enforced | ✅ | `test_platform_auditor_can_view_audit_logs_but_not_manage_tenants`, `test_platform_support_engineer_cannot_view_audit_logs_or_manage_tenants` |
| A platform user logging in lands on the platform console, not a broken tenant redirect loop | ✅ | Live-verified — login redirected straight to `/platform/tenants` |
| Backend tests pass | ✅ | **194/194** passing (`pytest -q` in `apps/api`, up from 180 — 13 new platform_admin tests + 1 new sync test), plus **12/12** in `packages/connector-sdk` |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 28/28 routes |

## Milestone 12 — Test Results (as actually executed in this session)

```
packages/connector-sdk: pytest -q     → 12 passed
apps/api: pytest -q                   → 194 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 28/28 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Next.js stack, driven by headless Chromium: logged in as
the seeded `platform.admin@gridkeep-platform.example` (`platform_super_admin`) and confirmed the redirect
landed on `/platform/tenants` directly (not `/dashboard`, not a `/select-workspace` loop); confirmed the
seeded Northstar Advisory Demo tenant appeared in the platform-wide list; changed its status to
`suspended` via the UI and confirmed it reflected immediately; opened `/platform/audit-logs` and confirmed
the `platform.tenant_status_changed` event appeared, correctly attributed to Northstar Advisory Demo, in a
list that is NOT scoped to any single tenant's RLS context; reverted the tenant's status back to `active`
to leave the demo environment as found.

## Milestone 12 — Architecture Decisions (made or refined during implementation)

- **Widening `audit_logs_select` rather than inventing a separate platform-audit table.** The audit trail
  already exists, is already fed by every module, and already has a (partially-wired) platform-admin RLS
  branch — extending that one policy is a smaller, more honest change than standing up a parallel
  cross-tenant audit mechanism, and it keeps "one append-only audit log" true rather than fragmenting it.
- **`platform_admin_scoped_session()` is a distinct session flavour from `tenant_scoped_session(...,
  is_platform_admin=True)`, not a parameter on it.** The existing flavour always pins a specific
  `tenant_id` (used by support-access grants and now tenant-status changes, where the audit write needs
  `tenant_id = app_current_tenant_id()` to satisfy the insert policy); the new one deliberately leaves
  `current_tenant_id` unset so the widened SELECT policy's OR clause is unconditionally true. Conflating
  the two would either weaken the tenant-pinned flavour's guarantees or fail to give the audit-log route
  the cross-tenant visibility it actually needs.
- **The tenant status state machine treats `archived` as terminal.** No route back was implemented; a
  platform admin who archives a tenant by mistake would need direct database access to undo it. This
  mirrors how a real deletion/closure boundary should behave — not a decision to revisit lightly, flagged
  explicitly below.
- **`update_tenant_status` reuses the exact session-variable pattern `create_grant`/`revoke_grant`
  established in Milestone 1** (`set_tenant_context(session, tenant_id, is_platform_admin=True)` on the
  route's own injected session, committed by the route) rather than introducing a second, parallel way to
  scope a platform-admin write — consistency with existing precedent over a "cleaner-looking" new
  abstraction.
- **Platform permissions are computed client-side from `platform_role_name`, exactly like tenant
  permissions are computed from `role_name`.** No new backend-computed-permissions endpoint was invented;
  `DEFAULT_PLATFORM_ROLE_PERMISSIONS` in the shared TS package is the single client-side source, kept in
  sync with Python by a dedicated test — same shape, same guarantee, as the tenant-role equivalent.

## Milestone 12 — Known Limitations

- **No route back from `archived`.** A tenant a platform admin archives by mistake cannot be reactivated
  through the API — this is by design (archived is meant to be terminal) but is worth your explicit
  sign-off, since it has no self-service recovery path.
- **Tenant detail is a bare summary, not an enriched view.** `GET /api/platform/tenants/{id}` returns the
  same fields as the list endpoint — no membership count, subscription plan, or asset counts. Adding those
  would require either widening `memberships`/`tenant_subscriptions` RLS further or a dedicated
  aggregation query, judged out of scope for this pass to keep the milestone coherent (the same reasoning
  Milestone 10 used to defer threat-intel/playbook integration).
- **No rate limiting specific to the audit-log or tenant-list endpoints** beyond the existing global
  limiter — a platform admin (by definition already a privileged, small population) could page through the
  full cross-tenant audit trail without a dedicated throttle.
- **No frontend automated tests were added for the new platform pages** — same gap and rationale as every
  prior milestone's new pages: verified manually end-to-end via Playwright, passes lint/typecheck/build,
  but no dedicated Vitest coverage.
- **Second-approver support-access flow is still unbuilt** (carried over from Milestone 1 — unrelated to
  this milestone's scope but adjacent, since it's the other half of `platform_admin`).

## Milestone 12 — Unresolved Risks

- Carried over from Milestones 1-11 (in-memory rate limiter, no second-approver support-access flow, no
  dependency/container/secret scanning in CI, Docker Compose still unverified end-to-end, the scoring
  formulas' simplicity, the inherent stakes of unattended action execution, the evidence
  permission-per-target design, the control-scoring weights, the `reports.view`/`findings.view`
  cross-cutting-permission decisions, the widened-RLS-by-data-value pattern, the threat-intel
  confidence-to-severity thresholds, the HTTP-file domain-verification substitution) — none were touched
  this milestone and remain open.
- **The widened `audit_logs_select` policy is a meaningful security-relevant change** — it expands what a
  platform-admin-flavoured session can see. The blast radius is bounded (only reachable through
  `get_platform_admin_db`, itself gated by `platform.audit.view`), but this is exactly the kind of RLS
  change that deserves your explicit review rather than quiet acceptance, per the same standard applied to
  every prior widened-SELECT decision.
- The tenant status transition graph (`_VALID_TENANT_STATUS_TRANSITIONS`) is a judgment call, not derived
  from any stated specification — same category of flag as the resilience/compliance scoring weights and
  the threat-intel severity thresholds in earlier milestones.

## Milestone 12 — Pending Approvals

- This Milestone 12 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps are documented rather than hidden.
- Recommend explicit review of the widened `audit_logs_select` RLS policy and the terminal-`archived`
  design (see Architecture Decisions and Unresolved Risks) — both are security/data-lifecycle-relevant
  decisions made in the absence of an explicit specification for this milestone.

## Milestone 12 — Next Action

Milestone 12 was approved and Milestone 13 is complete — see below.

## Milestone 13 — Completed Work

### The breadcrumb this milestone came from
- By Milestone 12 every permission in `security-contracts` — tenant *and* platform — was wired to a route,
  so the usual scope signal was exhausted for the third time running. A research pass found the strongest
  candidate yet: `User.mfa_totp_secret_encrypted`/`mfa_enabled`, `Session.mfa_verified`/`step_up_expires_at`,
  and `core.deps.require_step_up` have all existed since Milestone 1 — `require_step_up`'s own docstring
  named "disruptive-action approval" as its intended use case — but zero routes ever used any of it.
  `TenantSecurityProfile` (MFA/step-up policy toggles for a tenant) has existed just as long with its one
  read function (`repository.get_security_profile`) having zero callers anywhere in application code. This
  milestone builds the missing MFA subsystem and wires both idle mechanisms to something real.

### Backend
- **Real TOTP, not a placeholder.** `modules.identity.service` gained `enroll_mfa`/`confirm_mfa_enrollment`/
  `disable_mfa`/`verify_totp_code`, using `pyotp` (a new dependency) for actual RFC 6238 TOTP generation
  and verification — the same "a security control has to actually check something" standard Milestone 11
  held itself to for domain verification. The secret is encrypted at rest by reusing `credential_vault`'s
  existing envelope-encryption `VaultAdapter` (Milestone 1) rather than inventing a second encryption
  primitive; `EncryptedSecret`'s four fields are packed into the single `String(500)` column the schema
  already defined for exactly this purpose.
- **Enrollment is two-step by design**: `enroll_mfa` generates and stores the secret but leaves
  `mfa_enabled=False` until `confirm_mfa_enrollment` proves the authenticator app actually received it
  correctly — showing a secret proves nothing on its own, the same reasoning any real TOTP flow uses.
- **Login now issues a challenge, not a session, for MFA-enabled accounts.** A new `MfaChallengeToken`
  table (mirroring `PasswordResetToken`/`EmailVerificationToken`'s exact generate-hash-store-consume shape)
  is a short-lived, single-use proof that the password check already passed; `POST /api/auth/mfa/verify-login`
  consumes it plus a valid TOTP code to actually create the session. Deliberately its own table rather than
  a flag on `Session`, since the whole point is that no session exists yet.
- **`require_step_up` is wired into `approve_action_run`** — the exact call site its own docstring named
  since Milestone 1. It's conditional on `user.mfa_enabled`: unconditional enforcement would have locked
  every user who hasn't opted into MFA out of disruptive-action approval entirely, with no way to ever
  satisfy the gate, silently breaking every existing "approve a disruptive action" workflow. A user without
  MFA gets exactly the pre-Milestone-13 behaviour; a user with MFA enabled must have recently re-proven it
  via the new `POST /api/auth/step-up`.
- **`TenantSecurityProfile` finally has routes.** `GET`/`PATCH /api/tenancy/security-profile` (gated
  `settings.manage`) expose the `require_mfa_for_admins`/`require_step_up_for_disruptive_actions`/
  `session_ttl_seconds` toggles that have been readable-in-theory-but-never-read since Milestone 1.
- **`POST /api/auth/mfa/enroll|confirm|disable`**: self-service, tenant-agnostic (MFA belongs to the user,
  not any one workspace) — a platform user could enroll exactly the same way a tenant user does.

### Frontend (`apps/web`)
- Login page gained an MFA-challenge step: on `mfa_required: true`, prompts for a code and calls
  `/api/auth/mfa/verify-login` before completing sign-in.
- New `/settings/security` page: enroll/confirm/disable MFA for your own account, plus the tenant security
  policy toggles (for users who hold `settings.manage`).
- Automation page: an `approve` attempt that 403s with `step_up_required` now shows an inline "enter a
  fresh code" prompt, verifies it via `/api/auth/step-up`, then retries the approval — rather than just
  surfacing a raw error.

## Milestone 13 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| MFA enrollment generates a real TOTP secret and doesn't enable MFA until confirmed | ✅ | `test_enroll_and_confirm_mfa_happy_path`; live-verified |
| Confirming enrollment with the wrong code is rejected | ✅ | `test_confirm_mfa_with_wrong_code_is_rejected` |
| Login for an MFA-enabled account issues a challenge, not a session | ✅ | `test_login_with_mfa_enabled_requires_a_challenge` — confirms `/api/auth/me` is still 401 until the challenge is completed; live-verified |
| A wrong code at the login challenge is rejected | ✅ | `test_mfa_verify_login_with_wrong_code_is_rejected` |
| Disabling MFA requires the current valid code | ✅ | `test_disable_mfa_requires_the_correct_code` |
| Step-up requires MFA to be enabled first (can't step up what doesn't exist) | ✅ | `test_step_up_requires_mfa_enabled_first` |
| Approving a disruptive action with MFA enabled requires a fresh step-up; a valid one unblocks it | ✅ | `test_approve_action_run_requires_step_up_when_mfa_enabled`; live-verified — a real pending action, approved live via the Automation page's new step-up prompt |
| Users without MFA enabled see unchanged `approve_action_run` behaviour | ✅ | Full existing `test_actions_api.py::test_approve_and_reject_action_run` still passes unmodified |
| `TenantSecurityProfile` is finally readable and writable | ✅ | `test_security_profile_get_update_round_trip_and_permission_gating` |
| Backend tests pass | ✅ | **199/199** passing (`pytest -q` in `apps/api`, up from 194 — 8 new MFA tests, minus one now-covered-differently), plus **12/12** in `packages/connector-sdk` |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 29/29 routes |

## Milestone 13 — Test Results (as actually executed in this session)

```
packages/connector-sdk: pytest -q     → 12 passed
apps/api: pytest -q                   → 199 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 29/29 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Next.js stack, driven by headless Chromium, computing
real TOTP codes with `pyotp` exactly as an authenticator app would (nothing mocked): logged in as the demo
tenant owner without MFA; enabled MFA via `/settings/security`, reading the real generated secret straight
off the page and confirming with a correctly-computed code; logged out and back in, confirmed the login
flow now demanded a verification code before reaching the dashboard, and that a correct code completed it;
seeded a pending disruptive action (`isolate_endpoint`) as the analyst via the real API (the request-a-
disruptive-action mechanism itself is Milestone 4, not new here); attempted to approve it as the owner on
the live Automation page and confirmed the new step-up prompt appeared; entered a valid code and confirmed
the approval then went through. Demo environment reverted to its prior state (MFA disabled again, the test
action run removed) afterward.

## Milestone 13 — Architecture Decisions (made or refined during implementation)

- **Step-up enforcement is conditional on `user.mfa_enabled`, not universal.** The alternative — always
  requiring step-up on `approve_action_run` — would mean any tenant that has never enrolled anyone in MFA
  could never approve a disruptive action again, since there'd be no way to ever satisfy the gate. Scoping
  enforcement to users who've actually opted in preserves backward compatibility for everyone else while
  still giving the mechanism real teeth for the users who can satisfy it.
- **`TenantSecurityProfile.require_step_up_for_disruptive_actions` is now stored and readable, but
  `approve_action_run` doesn't read it back yet** — it always enforces step-up for MFA-enabled users
  regardless of this toggle's value. Making the toggle actually gate enforcement (e.g., forcing step-up
  even without the toggle, or explicitly allowing a tenant to turn it off) was judged a reasonable
  follow-up rather than blocking this milestone — see Known Limitations.
- **A dedicated `MfaChallengeToken` table, not a flag on `Session`.** A pre-MFA-verified login has, by
  definition, no session yet — reusing `Session` with an "unverified" flag would mean either creating a
  session before authentication is actually complete (contradicting how every other part of this codebase
  treats session issuance as the proof of a completed login) or bolting extra state onto a model whose
  entire shape assumes a completed login already happened.
- **The encrypted MFA secret reuses `credential_vault`'s existing `VaultAdapter`**, packed into the single
  column Milestone 1 already defined, rather than building a parallel encryption path — one production-
  swappable encryption primitive for the whole codebase, not two.
- **MFA enrollment is self-service and tenant-agnostic** — deliberately not gated by
  `require_mfa_for_admins`, which is stored but not yet enforced (see Known Limitations). Any authenticated
  user, tenant or platform, can enroll.

## Milestone 13 — Known Limitations

- **`require_mfa_for_admins` and `require_step_up_for_disruptive_actions` are stored and returned by the
  new security-profile routes, but neither is actually enforced yet.** No route currently checks
  `require_mfa_for_admins` to force enrollment, and `approve_action_run` doesn't read
  `require_step_up_for_disruptive_actions` to decide whether to skip the gate — it's driven purely by
  `user.mfa_enabled`. Wiring these toggles to actual enforcement is a reasonable, coherent follow-up milestone
  rather than an oversight; exposing them at all (from zero callers) was this milestone's actual scope.
  **[Resolved in Milestone 14: `require_mfa_for_admins` is now enforced in `get_tenant_context`
  (via `is_mfa_enrollment_required`) and `require_step_up_for_disruptive_actions` now gates
  `approve_action_run`. Found stale and corrected during Milestone 22's documentation-audit pass.]**
- **No backup/recovery codes.** A user who enables MFA and loses their authenticator device has no
  self-service recovery path — only a platform admin with direct database access could clear
  `mfa_totp_secret_encrypted` today. Reasonable, common future work.
- **No QR code image** — the enrollment response returns the raw secret and an `otpauth://` provisioning
  URI as text, not a rendered QR code. Most authenticator apps support manual secret entry, and adding
  server-side QR image generation was judged unnecessary complexity for this pass.
- **Step-up's `max_age_seconds`/`STEP_UP_TTL_SECONDS` (300s) is a judgment call**, not derived from any
  stated specification — same category of flag as the tenant-status transition graph and the threat-intel
  severity thresholds in earlier milestones.
- **No frontend automated tests were added for the new security settings page or the login MFA step** —
  same gap and rationale as every prior milestone's new pages: verified manually end-to-end via Playwright,
  passes lint/typecheck/build, but no dedicated Vitest coverage.

## Milestone 13 — Unresolved Risks

- Carried over from Milestones 1-12 (in-memory rate limiter, no dependency/container/secret scanning in
  CI, Docker Compose still unverified end-to-end, the scoring formulas' simplicity, the inherent stakes of
  unattended action execution, the evidence permission-per-target design, the control-scoring weights, the
  cross-cutting-permission decisions, the widened-RLS-by-data-value pattern, the threat-intel
  confidence-to-severity thresholds, the HTTP-file domain-verification substitution, the widened
  `audit_logs_select` policy, the terminal-`archived` tenant status) — none were touched this milestone
  and remain open. Note: the second-approver support-access workflow, carried over since Milestone 1 and
  re-flagged in Milestone 12, is still unbuilt — this milestone built MFA/step-up instead, a related but
  distinct hardening item.
- **The conditional (MFA-enabled-only) step-up enforcement is a deliberate compatibility choice, not a
  security ideal** — a tenant that wants to *mandate* step-up for all disruptive approvals regardless of
  individual MFA enrollment can't do that yet (see Known Limitations on `require_step_up_for_disruptive_actions`
  not being read back). Flagged for your explicit review since it's a real gap between what the toggle
  implies and what it currently does.
- The TOTP `valid_window=1` clock-skew tolerance (accepting the previous/next 30-second window) is a
  standard tradeoff, not a specified requirement — same judgment-call category as prior milestones' scoring
  weights and thresholds.

## Milestone 13 — Pending Approvals

- This Milestone 13 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps are documented rather than hidden.
- Recommend explicit review of the conditional (MFA-enabled-only) step-up enforcement and the still-inert
  `TenantSecurityProfile` toggles (see Architecture Decisions, Known Limitations, and Unresolved Risks) —
  both are security-relevant judgment calls made in the absence of an explicit specification for this
  milestone.

## Milestone 13 — Next Action

Milestone 13 was approved and Milestone 14 is complete — see below.

## Milestone 14 — Completed Work

### The breadcrumb this milestone came from
- Milestone 13's own Known Limitations named the exact gap: `TenantSecurityProfile.require_mfa_for_admins`
  and `require_step_up_for_disruptive_actions` were finally stored and readable via new routes, but neither
  actually governed anything — `approve_action_run` ignored the step-up toggle entirely, and nothing
  anywhere enforced MFA enrollment for admins. This milestone wires both up for real.

### Backend
- **`modules.tenancy.service.is_mfa_enrollment_required()`** (new, shared): the single place that decides
  whether a given role/tenant/user combination is currently required to have MFA enabled. Called from two
  places — `core.deps.get_tenant_context` (the real enforcement gate, blocking all tenant-scoped access)
  and `/api/auth/me`/login (an informational mirror so the frontend can redirect proactively instead of
  only discovering the block from a failed tenant API call).
- **`ADMIN_ROLE_NAMES = {"tenant_owner", "security_administrator"}`**: a deliberate, documented judgment
  call about which tenant roles count as "admin" for this toggle's purposes — the two roles with the
  broadest sensitive-permission surface (`actions.approve_disruptive`, `users.manage`,
  `trust_passport.manage`). Narrower admin-adjacent roles like `it_administrator` were left out.
- **A new `MfaEnrollmentRequiredError` (403)** raised by `get_tenant_context` itself — the same dependency
  every tenant-scoped route already depends on for tenant/membership/role resolution — so an admin without
  MFA is blocked from *all* tenant reads and writes alike, not just disruptive ones. Enrolling MFA remains
  possible while blocked, since `/api/auth/mfa/enroll`/`confirm` only need `AuthContext`, never
  `TenantContext`.
- **A critical default-value fix discovered during implementation, before any real enforcement shipped**:
  `TenantSecurityProfile.require_mfa_for_admins` had defaulted to `True` since Milestone 1 — harmless while
  unenforced, but wiring real enforcement against that default would have locked every freshly-onboarded
  tenant owner out of their own brand-new workspace immediately after signup, with literally no way to
  satisfy the gate (this was caught by the full test suite going from 199 green to 10 broken the moment
  enforcement was wired, tracing every failure back to the same onboarding-then-immediately-blocked
  pattern). Changed the default to `False` — an admin now has to deliberately opt in to requiring MFA for
  their tenant, exactly mirroring how MFA enrollment itself is opt-in. `require_step_up_for_disruptive_actions`
  needed no such change: `require_step_up` only ever consults it for users who already have MFA enabled, so
  an unenrolled user is unaffected by its default either way.
- **`require_step_up` now reads `require_step_up_for_disruptive_actions`** before enforcing anything: if a
  tenant has explicitly turned it off, an MFA-enabled admin can approve a disruptive action without a
  fresh step-up, restoring the pre-Milestone-13 behaviour on request. The dependency now requires a
  resolved `TenantContext` (previously tenant-agnostic) — a real coupling, documented in its own docstring,
  that matches its one actual caller today.

### Frontend (`apps/web`)
- `(tenant)/layout.tsx` now redirects to `/settings/security` whenever `mfa_enrollment_required` is true —
  the same pattern already used for the `active_membership_id` redirect — rather than letting every
  tenant page's data fetch fail with a raw 403.
- The security settings page shows a clear banner when landed on because of this block, and the workspace
  policy card shows a specific "enable MFA above to unlock this" message instead of an indefinite
  "Loading…" while the block is in effect.
- Login redirects straight to `/settings/security` when the login response itself already carries
  `mfa_enrollment_required: true`, skipping the extra hop through `/dashboard`.

## Milestone 14 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| A newly-onboarded tenant defaults to NOT requiring MFA for admins | ✅ | `test_new_tenant_defaults_to_require_mfa_for_admins_off` |
| An admin without MFA is blocked from all tenant-scoped access once the tenant requires it | ✅ | `test_admin_without_mfa_is_blocked_once_tenant_requires_it`; live-verified against the demo tenant's pre-existing `require_mfa_for_admins=True` row |
| The blocked admin can still enroll MFA and immediately regain access | ✅ | Same test, plus live-verified — no re-login required after confirming enrollment |
| An admin who already has MFA enabled is unaffected by the toggle | ✅ | `test_admin_with_mfa_already_enabled_is_unaffected_by_the_toggle` |
| Non-admin roles are never blocked by the toggle | ✅ | `test_non_admin_role_is_never_blocked_by_the_toggle` |
| `/me` and login expose `mfa_enrollment_required` so the frontend can redirect proactively | ✅ | `test_login_and_me_expose_mfa_enrollment_required`; live-verified — direct redirect to `/settings/security` from both login and a direct dashboard navigation |
| Turning off `require_step_up_for_disruptive_actions` lets an MFA-enabled admin approve without stepping up | ✅ | `test_require_step_up_toggle_off_lets_mfa_enabled_admin_approve_without_step_up`; live-verified — approval succeeded directly, no step-up prompt appeared |
| Backend tests pass | ✅ | **205/205** passing (`pytest -q` in `apps/api`, up from 199 — 6 new tests), plus **12/12** in `packages/connector-sdk` |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 29/29 routes |

## Milestone 14 — Test Results (as actually executed in this session)

```
packages/connector-sdk: pytest -q     → 12 passed
apps/api: pytest -q                   → 205 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 29/29 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Next.js stack, driven by headless Chromium: the demo
tenant's own `tenant_security_profiles` row happened to already carry `require_mfa_for_admins=True` (a
leftover from before this milestone's default-value fix), so logging in as the demo owner without MFA
enrolled reproduced the real block live without needing to toggle anything — login redirected straight to
`/settings/security`, the blocking banner appeared, and navigating directly to `/dashboard` bounced straight
back. Enrolled MFA with a real computed TOTP code; the workspace policy card (previously erroring) and
`/dashboard` were both immediately reachable with no re-login. Separately, turned off
`require_step_up_for_disruptive_actions`, logged back in through the MFA challenge, and confirmed a
disruptive action approved directly with no step-up prompt. Demo environment reverted to its prior state
(MFA disabled, toggles restored, test action run removed) afterward.

## Milestone 14 — Architecture Decisions (made or refined during implementation)

- **`is_mfa_enrollment_required` is a single shared function, called from both the real enforcement gate
  and the informational `/me` flag**, rather than two separate implementations. Keeping the "what counts
  as blocked" logic in exactly one place means the frontend's proactive redirect and the backend's actual
  block can never silently drift out of sync with each other.
- **Enforcement lives inside `get_tenant_context` itself, not a separate opt-in dependency** like
  `require_tenant_write`. MFA-for-admins is an identity-assurance gate, not a write-specific one — an
  insufficiently-authenticated admin shouldn't be trusted to read sensitive tenant data either, so every
  tenant route needed to inherit the check automatically rather than requiring each route to remember to
  add it.
- **Changing `require_mfa_for_admins`'s default from `True` to `False` was a necessary correction, not
  scope creep.** A default that silently locks out every new tenant's own owner immediately after signup —
  with no self-service way to ever satisfy the gate, since the block itself prevents the very settings page
  that would let them fix it via a *different* route than MFA enrollment — is not a viable default for a
  feature the tenant is meant to opt into. This was caught by the existing test suite immediately, not
  discovered later.
- **`require_step_up` now requires a resolved `TenantContext`**, coupling it to tenant-scoped routes. Its
  one real caller (`approve_action_run`) already needed one; a hypothetical future non-tenant use (the
  credential-vault-access example in its own docstring since Milestone 1) would need a separate variant
  rather than forcing this one to stay artificially generic.

## Milestone 14 — Known Limitations

- **The admin-role set (`tenant_owner`, `security_administrator`) is a fixed, hardcoded judgment call**,
  not configurable per tenant and not derived from a formal permission-based heuristic. A tenant that
  considers a different role "sensitive enough" to require MFA for has no way to express that.
- **No grace period.** The moment `require_mfa_for_admins` is turned on, any admin without MFA is blocked
  on their very next request — including, in principle, the admin who just turned the toggle on, if they
  hadn't already enrolled MFA themselves first. There's no "you have N days to enroll" warning window.
- **The self-lockout risk this creates for platform support was not specifically addressed** — a support
  engineer helping a fully-locked-out tenant would need the existing (already-limited) support-access grant
  mechanism, not anything new built this milestone.
- **No frontend automated tests were added for the new enforcement UX** — same gap and rationale as every
  prior milestone's new pages: verified manually end-to-end via Playwright, passes lint/typecheck/build,
  but no dedicated Vitest coverage.

## Milestone 14 — Unresolved Risks

- Carried over from Milestones 1-13 (in-memory rate limiter, no dependency/container/secret scanning in
  CI, Docker Compose still unverified end-to-end, the scoring formulas' simplicity, the inherent stakes of
  unattended action execution, the evidence permission-per-target design, the control-scoring weights, the
  cross-cutting-permission decisions, the widened-RLS-by-data-value pattern, the threat-intel
  confidence-to-severity thresholds, the HTTP-file domain-verification substitution, the widened
  `audit_logs_select` policy, the terminal-`archived` tenant status, the second-approver support-access
  workflow, MFA backup/recovery codes) — none were touched this milestone and remain open.
- **The hardcoded admin-role set is a real judgment call with security implications** — flagged explicitly
  for your review, since a tenant relying on a different role structure (e.g. a custom-permissioned
  variant of `it_administrator` with `users.manage`) would find that role silently exempt from this
  protection.
- **No self-lockout safety valve beyond MFA enrollment itself remaining reachable.** If a future change
  ever made MFA enrollment routes themselves tenant-scoped, this would become a genuine dead end — worth
  keeping in mind as a design invariant, not just an implementation detail, in any future refactor of the
  auth dependency chain.

## Milestone 14 — Pending Approvals

- This Milestone 14 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps are documented rather than hidden.
- Recommend explicit review of the hardcoded admin-role set and the `require_mfa_for_admins` default-value
  change (see Architecture Decisions, Known Limitations, and Unresolved Risks) — both are security-relevant
  judgment calls made in the absence of an explicit specification for this milestone.

## Milestone 14 — Next Action

Awaiting your review. Once you're satisfied, send **`APPROVE MILESTONE 15`** to begin the next milestone.

## Milestone 15 — Completed Work

### The breadcrumb this milestone came from
- Milestone 14's own Unresolved Risks explicitly carried forward "the second-approver support-access
  workflow" as an untouched open item. Independent verification found the gap was real and specific:
  `create_grant` set `approved_by_user_id` to the very same platform user who requested the grant, with
  `status="active"` immediately — no second person was ever actually involved, despite
  `SupportAccessGrant`'s own docstring describing a proper approval workflow. There was also no
  platform-wide list endpoint at all (only "create", "revoke", and a tenant-side "list my grants"), so a
  genuine second approver would have had no way to discover a pending request in the first place.

### Backend
- **`create_grant` now produces a `pending` grant with no `approved_by_user_id`, `starts_at`, or
  `expires_at`** — the requested duration is stored separately (`requested_duration_hours`) and only
  applied once approved. **`approve_grant`** (new) is the second-approver check this milestone exists for:
  it rejects a grant that isn't currently `pending` (409) and rejects the requester approving their own
  request (422), then activates it, stamping `starts_at`/`expires_at` from the stored duration.
- **Rejecting a still-pending request needed no new function** — the existing `revoke_grant` never checked
  prior status, so it already worked correctly as a rejection path for a `pending` grant, not just as a
  revocation of an `active` one.
- **A new platform-wide `list_all_grants` / `GET /api/platform/support-access-grants`**, filterable by
  tenant and status, is the cross-tenant discovery surface a second approver needs. It's reachable only
  through `get_platform_admin_db` (Milestone 12's platform-admin-scoped session), because the underlying
  RLS policy on `support_access_grants` was widened — SELECT now allows `tenant_id = app_current_tenant_id()
  OR app_is_platform_admin()`, with INSERT/UPDATE/DELETE staying strictly tenant-scoped — the same
  widened-SELECT shape used for `trust_passport_settings` (M9), `audit_logs` (M12), and now this table.
- **`resolve_user_emails`** (new): a single batched `users` lookup that resolves `platform_user_id`,
  `requested_by_user_id`, and `approved_by_user_id` to emails for every grant returned by any of the three
  read endpoints (platform-wide list, tenant list, create/approve/revoke responses) — raw UUIDs weren't
  real transparency despite the model's own docstring promising tenant-visible grants. `users` carries no
  RLS (identity isn't tenant-owned), so this works regardless of which session flavour is calling it.
- Chose **`platform.support_access` as the sole gating permission for both request and approve** — any two
  different holders of that permission can request/approve each other's grants — rather than inventing a
  separate, more senior "approver" permission. A documented judgment call, not a more elaborate two-tier
  scheme.

### Frontend (`apps/web`)
- New `/platform/support-access` page: request a grant against a tenant (tenant picker sourced from the
  existing `GET /api/platform/tenants`, reason, duration), filter by status, and Approve/Reject/Revoke each
  grant. The Approve button is disabled for the requester's own pending request — mirroring the backend's
  self-approval rejection for good UX even though the backend enforces it regardless. Added "Support
  Access" to `PlatformShell`'s nav, between "Tenants" and "Audit Log".
- A new "Platform Support Access" card on the tenant-side `/settings/security` page (gated on
  `settings.manage`, consistent with the existing tenant-facing `GET /api/support-access-grants` endpoint)
  shows every grant against that workspace — status, reason, requester, and approver — using the newly
  resolved emails instead of raw IDs.

## Milestone 15 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| A new support access request starts `pending`, with no approver or active window | ✅ | `test_platform_admin_can_request_approve_and_revoke_support_access` |
| The requester cannot approve their own request | ✅ | Same test (422); live-verified — Approve button disabled in the UI for the requester |
| A different platform admin can approve a pending request, activating it with the stored duration | ✅ | Same test; live-verified — a second platform admin (`platform_support_engineer` role) approved live and the grant became `active` with correct `expires_at` |
| Approving a grant that isn't pending is rejected | ✅ | `test_cannot_approve_a_grant_that_is_not_pending` (409) |
| A pending request can be rejected via the existing revoke path | ✅ | Covered by `test_platform_admin_can_request_approve_and_revoke_support_access` |
| A platform-wide list spans multiple tenants in one call (exercises the widened RLS) | ✅ | `test_platform_wide_support_access_grants_list_spans_multiple_tenants` |
| A platform role without `platform.support_access` cannot request, approve, or list grants | ✅ | `test_platform_auditor_cannot_request_or_list_support_access_grants` |
| The tenant can see every grant against its own workspace, including who requested/approved it | ✅ | Live-verified — demo tenant owner's `/settings/security` page showed both the `active` and still-`pending` grants with resolved requester/approver emails |
| Backend tests pass | ✅ | **208/208** passing (`pytest -q` in `apps/api`, up from 205 — 3 net new tests), `ruff check .` clean |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 31/31 routes |

## Milestone 15 — Test Results (as actually executed in this session)

```
apps/api: pytest -q                   → 208 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 31/31 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Next.js stack, driven by headless Chromium, using a
second platform-admin account created for this purpose (`platform_support_engineer` role — the seeded demo
environment only ships one platform admin). As the first platform admin: requested access against the
demo tenant, confirmed the grant showed `pending` with no approver, and confirmed the Approve button was
disabled for that same admin's own request. Logged out, logged in as the second platform admin, confirmed
Approve was enabled there, approved it live, and confirmed the grant became `active` with the correct
`expires_at` and `approved_by` email. Logged in as the demo tenant owner and confirmed `/settings/security`
showed the grant with both the requester's and approver's emails correctly attributed. Test grants were
removed from the database afterward so the demo environment isn't left with stale support-access rows.

## Milestone 15 — Architecture Decisions (made or refined during implementation)

- **Rejection of a pending request reuses `revoke_grant` rather than introducing a separate `reject_grant`.**
  `revoke_grant` never checked prior status, so it already behaved correctly as a rejection path — adding a
  parallel function would have meant two code paths doing the same state transition (`status="revoked"`)
  for no behavioural difference.
- **The second-approver check is a single equality comparison
  (`grant.requested_by_user_id == approver_user_id`), not a role-based or seniority-based rule.** Any two
  distinct holders of `platform.support_access` can request/approve for each other. This keeps the
  permission model flat and matches how the pre-existing `platform_super_admin` /
  `platform_security_operator` / `platform_support_engineer` roles already share that single permission.
- **The platform-wide list endpoint reuses the exact widened-SELECT-RLS pattern from Milestone 12's audit
  log** rather than inventing a new cross-tenant access mechanism — `get_platform_admin_db` is now the
  established, single way any platform read endpoint gets to see more than one tenant's rows.
- **Deliberately did not build grant-gated tenant-data-read enforcement in this milestone.** The
  `SupportAccessGrant` model's own docstring references a `require_support_access_grant` dependency in
  `core/deps.py` that has never existed, and `is_grant_active()` has zero callers anywhere in the codebase.
  Actually gating some real platform read capability behind an active grant would mean inventing what that
  capability is — a materially larger scope than fixing the approval workflow itself, and left as an
  explicit Known Limitation below rather than attempted partially.

## Milestone 15 — Known Limitations

- **An active support access grant still gates nothing.** No platform code path currently checks
  `is_grant_active()` (it has zero callers) before letting a platform admin read or act on tenant data —
  the grant is an audited, tenant-visible record of intent, not yet an enforced access boundary. This is
  the same gap the model's docstring has described since it was first written; this milestone fixed the
  approval workflow around it but did not close it.
- **No automatic expiry sweep.** An `active` grant whose `expires_at` has passed simply stops being
  meaningful in principle — nothing revokes it, marks it `expired`, or hides it from the "active" filter.
  Since nothing currently reads grants to gate access, this has no live consequence yet, but would need
  addressing before the grant becomes a real enforcement mechanism.
  **[Corrected in Milestone 17: this claim was factually wrong. `worker.tasks.expire_support_access_grants`
  has existed since Milestone 1, runs every 5 minutes via Celery Beat, and correctly flips expired `active`
  grants to `expired`. This limitation was never re-verified against the actual worker code before being
  written — see Milestone 17's own notes for how this was caught and what the real remaining gap was.]**
- **The second platform admin used for live verification was created ad hoc for this session** (not part of
  `seed/demo.py`), since the seed script has only ever created one platform user. The seed script itself
  was intentionally left unchanged to avoid scope creep; a real second demo platform admin would need to be
  a deliberate seed-data decision, not a side effect of testing this milestone.
- **No frontend automated tests were added for the new pages** — same gap and rationale as every prior
  milestone's new UI: verified manually end-to-end via Playwright, passes lint/typecheck/build, but no
  dedicated Vitest coverage.

## Milestone 15 — Unresolved Risks

- Carried over from Milestones 1-14 (in-memory rate limiter, no dependency/container/secret scanning in
  CI, Docker Compose still unverified end-to-end, the scoring formulas' simplicity, the inherent stakes of
  unattended action execution, the evidence permission-per-target design, the control-scoring weights, the
  cross-cutting-permission decisions, the widened-RLS-by-data-value pattern, the threat-intel
  confidence-to-severity thresholds, the HTTP-file domain-verification substitution, the widened
  `audit_logs_select` policy, the terminal-`archived` tenant status, the hardcoded MFA admin-role set, MFA
  backup/recovery codes) — none were touched this milestone and remain open.
- **A support access grant being `active` still doesn't gate any real platform capability** — flagged
  explicitly for your review, since this means the approval workflow this milestone built is currently
  process/audit value only, not a technical access boundary. Closing that gap would require defining what
  platform reads/actions actually need to check for an active grant, which is a genuinely open product
  question, not just an implementation detail.
- **No expiry sweep** means an old `active` grant's `expires_at` having passed is not currently visible or
  actionable anywhere except by a human reading the timestamp themselves.
  **[Corrected in Milestone 17: false — a real sweep has existed since Milestone 1. See that milestone's
  notes.]**

## Milestone 15 — Pending Approvals

- This Milestone 15 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps are documented rather than hidden.
- Recommend explicit review of the decision to leave grant-gated access enforcement unbuilt (see
  Architecture Decisions, Known Limitations, and Unresolved Risks) — the grant workflow is now correct and
  auditable, but an `active` grant does not yet unlock anything on its own.

## Milestone 15 — Next Action

Awaiting your review. Once you're satisfied, send **`APPROVE MILESTONE 16`** to begin the next milestone.

## Milestone 16 — Completed Work

### The breadcrumb this milestone came from
- Milestone 15's own Architecture Decisions and Known Limitations sections named this gap explicitly:
  `SupportAccessGrant`'s docstring has promised since it was first written that "every platform_admin read
  of tenant data must resolve an active grant row here first (see deps.py `require_support_access_grant`)"
  — but that dependency never existed anywhere in `core/deps.py`, and `is_grant_active()` had zero callers.
  Milestone 15 deliberately left this unbuilt, flagging it as the natural next step rather than attempting
  it as scope creep. This milestone builds both halves: the dependency itself, and the first real
  platform-admin read it gates.

### Backend
- **`core.deps.require_support_access_grant()`** (new): reads `tenant_id` from the same path parameter the
  route declares (FastAPI resolves path parameters across the whole dependency tree), composes with
  `require_platform_permission("platform.support_access")` so the permission check happens first, then
  calls `is_grant_active`. Deliberately shares its `get_db` session with the route handler — FastAPI caches
  a dependency's result per request, so `is_grant_active`'s `set_tenant_context(db, tenant_id,
  is_platform_admin=True)` call already leaves the session correctly scoped for the route's own queries
  afterward, the same "set context once, reuse the session" pattern `update_tenant_status`/`create_grant`
  established.
- **`GET /api/platform/tenants/{tenant_id}/workspace-snapshot`** (new): the actual read this whole grant
  workflow exists to gate. Returns the tenant's member list (email, name, role, status) and open
  findings/incidents/connected-integrations counts. Reuses `modules.findings.get_risk_summary` and
  `modules.incidents.get_incident_summary` directly — the same per-module summary functions
  `modules.reporting`'s executive summary already composes — rather than re-deriving what "open" means for
  a second time.
- **Every successful snapshot fetch is itself audit-logged** as `platform.support_access_used`, fulfilling
  the model's other long-standing docstring promise ("every grant is itself an audited event (both
  creation and each use)") — creation, approval, and revocation were already audited; this milestone adds
  the missing fourth event.
- No schema change and no migration — this is a pure read composition over existing tables plus one new
  dependency function, the same shape Milestone 8's `modules.reporting` took.

### Frontend (`apps/web`)
- New `/platform/tenants/[tenantId]/workspace` page: tenant name/status, three summary tiles (open
  findings, open incidents, connected integrations), and a member table. Shows a clear "you need an active
  grant" message with a link back to Support Access when the backend returns
  `support_access_grant_required`, rather than a generic error.
- The Support Access page gained a "View workspace" button on a platform admin's own `active` grants,
  linking straight to the snapshot for that tenant.

## Milestone 16 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| A platform admin with no grant for a tenant cannot view its workspace snapshot | ✅ | `test_workspace_snapshot_requires_an_active_grant` (403, `support_access_grant_required: true`); live-verified |
| A grant that is only `pending` (not yet approved) still blocks the view | ✅ | `test_workspace_snapshot_denied_while_grant_is_still_pending`; live-verified |
| Once approved by a different admin, the original requester can view the snapshot | ✅ | `test_workspace_snapshot_accessible_with_an_active_grant`; live-verified end-to-end (request → block → approve by a second admin → view) |
| A revoked grant blocks the view again | ✅ | `test_workspace_snapshot_denied_after_grant_is_revoked` |
| A platform role without `platform.support_access` cannot reach the endpoint regardless of any grant | ✅ | `test_tenant_user_cannot_view_platform_workspace_snapshot_endpoint` |
| Each snapshot fetch is recorded in the platform audit log as `platform.support_access_used` | ✅ | `test_workspace_snapshot_use_is_audit_logged`; live-verified via direct query against the platform-wide audit log |
| The snapshot shows accurate member and open-findings/incidents/integrations data | ✅ | Live-verified against the demo tenant (5 members, 6 open findings, 0 open incidents, 5 connected integrations, matching direct DB state) |
| Backend tests pass | ✅ | **214/214** passing (`pytest -q` in `apps/api`, up from 208 — 6 new tests), `ruff check .` clean |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 32/32 routes |

## Milestone 16 — Test Results (as actually executed in this session)

```
apps/api: pytest -q                   → 214 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 32/32 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Next.js stack, driven by headless Chromium, using the
same two platform-admin accounts as Milestone 15's verification. Confirmed the workspace view was blocked
both before any grant existed and while a grant was still `pending`; requested access as one admin, approved
it as a different admin, and confirmed the original requester could then view the tenant's real member list
and open-findings/incidents/connected-integrations counts; confirmed the "View workspace" button on the
Support Access page navigates correctly; confirmed each fetch appeared in the platform-wide audit log as
`platform.support_access_used`, attributed to the correct actor.

This verification pass caught a real bug in the verification setup itself, not in the shipped code: an
`active` support-access grant left over from Milestone 15's own E2E session (created against the demo
tenant, with a 4-hour window) was still valid at the start of this session and caused the very first
E2E run to see the workspace snapshot when the intended test scenario was "no grant exists yet." Tracing it
down surfaced a genuine operational gotcha worth documenting: Milestone 15's end-of-session cleanup script
called `delete(SupportAccessGrant)` on a plain session with **no tenant context set** — since
`support_access_grants`' DELETE policy requires `tenant_id = app_current_tenant_id()` with no
platform-admin override, that delete silently affected zero rows despite reporting success, leaving three
grants (including one still-active) behind. Cleaned up correctly this time by calling
`set_tenant_context(session, tenant_id, is_platform_admin=True)` before the delete. See Known Limitations.

## Milestone 16 — Architecture Decisions (made or refined during implementation)

- **`require_support_access_grant` reads `tenant_id` as a bare path-parameter dependency rather than
  requiring the route to pass it explicitly.** FastAPI resolves path parameters identically regardless of
  which function in the dependency tree declares them, so the checker and the route handler both receive
  the same value with no risk of one being stale relative to the other.
- **Deliberately shares its DB session with the route handler instead of opening a second one.** The
  alternative (a separate session for the grant check) would need to duplicate
  `set_tenant_context` a second time in the route itself; sharing the session means the tenant-scoping
  side effect of checking the grant is exactly the tenant-scoping the subsequent queries need, with no
  duplication.
- **The workspace snapshot reuses `findings_service.get_risk_summary` and
  `incidents_service.get_incident_summary` verbatim** rather than re-querying `Finding`/`Incident` directly
  with a fresh "open" definition. This is the same discipline `modules.reporting` (Milestone 8) already
  established: one place decides what "open" means per domain, and every consumer (executive summary,
  now the support snapshot) calls it rather than re-deriving it.
- **Chose a single aggregate snapshot endpoint over several narrower ones** (e.g. separate
  members/findings/incidents endpoints) — a platform admin using an active grant needs the whole picture at
  once to actually help a tenant, and one audited "use" event per page view is clearer than several.

## Milestone 16 — Known Limitations

- **The snapshot is read-only and narrow by design** — members and three summary counts, not full
  findings/incidents/asset detail. Expanding it to deeper drill-down views is a natural next increment but
  wasn't attempted here to keep the milestone scoped to closing the specific gap Milestone 15 flagged.
- **No UI-level indication of how much time is left on the active grant** on the workspace snapshot page
  itself — the expiry is visible on the Support Access page but not repeated on the snapshot view a platform
  admin is actually looking at while doing support work.
  **[Resolved in Milestone 17: the snapshot response now includes `access_expires_at`, shown directly on
  the workspace page.]**
- **Bulk mutations against RLS-protected tables must set tenant context first, or they silently no-op.**
  This isn't a new limitation introduced this milestone, but this milestone's own E2E verification is what
  surfaced it concretely (see Test Results) — worth calling out as a standing operational hazard for any
  future ad-hoc cleanup script against this schema, not just support-access grants.
- **No automatic expiry sweep still applies** (carried from Milestone 15) — an expired-but-still-`active`
  grant row would still read as inactive correctly via the `expires_at > now()` check in `is_grant_active`,
  but nothing proactively transitions its `status` to reflect that.
  **[Corrected in Milestone 17: this claim, inherited from Milestone 15, was factually wrong — a real
  sweep (`worker.tasks.expire_support_access_grants`) has existed since Milestone 1. See Milestone 17's
  notes for how this was caught during that milestone's own scoping research.]**
- **No frontend automated tests were added for the new page** — same gap and rationale as every prior
  milestone's new UI: verified manually end-to-end via Playwright, passes lint/typecheck/build, but no
  dedicated Vitest coverage.

## Milestone 16 — Unresolved Risks

- Carried over from Milestones 1-15 (in-memory rate limiter, no dependency/container/secret scanning in
  CI, Docker Compose still unverified end-to-end, the scoring formulas' simplicity, the inherent stakes of
  unattended action execution, the evidence permission-per-target design, the control-scoring weights, the
  cross-cutting-permission decisions, the widened-RLS-by-data-value pattern, the threat-intel
  confidence-to-severity thresholds, the HTTP-file domain-verification substitution, the widened
  `audit_logs_select` policy, the terminal-`archived` tenant status, the hardcoded MFA admin-role set, MFA
  backup/recovery codes) — none were touched this milestone and remain open. (The "no expiry sweep for
  support access grants" item previously listed here has been removed — it was factually wrong; see the
  Milestone 17 correction note above.)
- **The workspace snapshot is currently the only grant-gated read** — if future milestones add more
  platform-admin-facing tenant data views, each will need to independently remember to apply
  `require_support_access_grant`, since there's no single enforcement point (like a router-level dependency)
  that would make forgetting it impossible.
- **The RLS-silently-no-ops-without-tenant-context hazard** (see Known Limitations) applies to every
  RLS-protected table, not just this one — flagged explicitly since it's a real footgun for anyone (human or
  agent) writing a one-off script against this database in the future.

## Milestone 16 — Pending Approvals

- This Milestone 16 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps are documented rather than hidden.
- Recommend explicit review of the decision to scope the snapshot narrowly (members + three counts) rather
  than building deeper drill-down views in the same milestone.

## Milestone 16 — Next Action

Awaiting your review. Once you're satisfied, send **`APPROVE MILESTONE 17`** to begin the next milestone.

## Milestone 17 — Completed Work

### The breadcrumb this milestone came from
- Milestone 15's and Milestone 16's own Known Limitations both claimed "no automatic expiry sweep exists"
  for support access grants. Before implementing against that claim, research confirmed it was **factually
  wrong**: `worker.tasks.expire_support_access_grants` has existed since Milestone 1, runs every 5 minutes
  via Celery Beat (`schedules.BEAT_SCHEDULE`), and correctly flips expired `active` grants to `expired`.
  The Known Limitations text had been carried forward across two milestones without being re-verified
  against the actual worker code. Live-verified this milestone by backdating a real grant's `expires_at`
  and invoking the actual sweep task, confirming it flips the status exactly as designed (see Test Results).
- With that false lead ruled out, research turned up the real gap: `SUPPORT_ACCESS_STATUSES`
  (`modules.platform_admin.models`) has existed since Milestone 15 but was never consulted anywhere — not
  by the TypeScript/Python security-contracts sync (every sibling status vocabulary, `TENANT_STATUSES`,
  is synced there), not by the `status` column itself (a plain `String(20)` since Milestone 1, unlike every
  sibling status column — `finding_status`, `incident_status`, `tenant_integration_status`,
  `tenant_status` — which are real Postgres enums), and not by the frontend (the status filter dropdown on
  `/platform/support-access` was missing "Expired" as an option entirely, despite the sweep actively
  setting it every 5 minutes).

### Backend
- **`SUPPORT_ACCESS_STATUSES` moved into `core/security_contracts.py`** as the canonical source (mirroring
  `TENANT_STATUSES`), with a matching TypeScript array in `packages/security-contracts/src/index.ts` and a
  new sync test (`test_support_access_statuses_match`).
- **`SupportAccessGrant.status` converted from `String(20)` to a real Postgres enum**
  (`support_access_grant_status`) via migration, closing the actual gap the dormant tuple should have
  prevented from the start. The migration casts the existing column in place
  (`ALTER COLUMN status TYPE ... USING status::...`) — safe with no backfill, since the worker has only
  ever written the four values in `SUPPORT_ACCESS_STATUSES`.
- **`is_grant_active` replaced with `get_active_grant`**, returning the grant row itself instead of a bare
  bool, so `require_support_access_grant` can surface the grant's real `expires_at` to the route — the
  workspace snapshot response now includes `access_expires_at`, the calling admin's own remaining access
  window, not just a pass/fail gate.

### Frontend (`apps/web`)
- The Support Access page's status filter dropdown now sources its options from the shared
  `SUPPORT_ACCESS_STATUSES` contract instead of a hardcoded three-item list, so "Expired" is finally a real,
  selectable filter — a support engineer can now actually find expired grants instead of only seeing them
  mixed into "All statuses" with no way to isolate them.
- The workspace snapshot page now shows "Your access expires ..." alongside the read-only-view label, using
  the new `access_expires_at` field.

## Milestone 17 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| `SUPPORT_ACCESS_STATUSES` is synced between Python and TypeScript like every other status vocabulary | ✅ | `test_support_access_statuses_match` |
| The `status` column rejects a value outside the enum at the database level | ✅ | `test_support_access_grant_status_column_rejects_invalid_values` (raises `DBAPIError`) |
| Migration round-trips cleanly (upgrade → downgrade → upgrade) | ✅ | Verified directly in this session against the live demo database |
| The workspace snapshot response includes the calling admin's own access expiry | ✅ | `test_workspace_snapshot_access_expires_at_matches_the_grant`; live-verified — exact match against the grant's stored `expires_at` |
| The frontend status filter includes "Expired" as a real, selectable option | ✅ | Live-verified via Playwright — dropdown options are `['All statuses', 'Pending', 'Active', 'Expired', 'Revoked']` |
| The real Celery sweep task correctly flips an expired `active` grant to `expired`, and the UI reflects it | ✅ | Live-verified — backdated a real grant's `expires_at`, invoked `worker.tasks._expire_support_access_grants_async` directly, confirmed `expired count: 1`, then confirmed the grant appears when filtering by "Expired" in the live UI |
| Access is denied the instant `expires_at` passes, independent of the sweep's cadence | ✅ | Live-verified — workspace snapshot returned 403 immediately after backdating `expires_at`, before the sweep had run at all |
| Backend tests pass | ✅ | **217/217** passing (`pytest -q` in `apps/api`, up from 214 — 3 new tests), `ruff check .` clean |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 32/32 routes |

## Milestone 17 — Test Results (as actually executed in this session)

```
apps/api: pytest -q                   → 217 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 32/32 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Next.js stack, driven by headless Chromium: requested and
approved a 1-hour grant through the real UI (two different platform admins, as always), confirmed the
status filter dropdown listed "Expired" as an option, and confirmed the workspace snapshot page showed
"Your access expires ...". Then, directly against the database, backdated that grant's `expires_at` into
the past and confirmed the workspace snapshot endpoint immediately returned 403 — proving access
enforcement never depended on the sweep having run. Invoked the actual worker task
(`worker.tasks._expire_support_access_grants_async`, imported and awaited directly, not a mock) and
confirmed it returned `expired count: 1` and flipped the row's `status` to `expired`. Filtered the live UI
by "Expired" and confirmed the grant appeared with the correct badge, reason, and attribution. Removed the
test grant afterward (this time correctly, with `set_tenant_context` called first — see Milestone 16's own
documented lesson about this).

## Milestone 17 — Architecture Decisions (made or refined during implementation)

- **Verified the "no expiry sweep" claim against the actual worker code before building anything against
  it.** Two consecutive milestones' Known Limitations had repeated the same claim without re-checking it;
  treating a prior milestone's own documentation as ground truth without verification would have led to
  building a redundant, possibly conflicting second sweep mechanism. The correction is recorded in place in
  Milestones 15 and 16's own sections rather than silently rewritten, per the standing discipline of
  documenting mistakes honestly rather than hiding them.
- **`SUPPORT_ACCESS_STATUSES` was moved into `core/security_contracts.py` and imported directly by
  `modules.platform_admin.models`**, rather than kept as a second locally-duplicated tuple the way
  `TENANT_STATUSES` exists in both `core/security_contracts.py` and `modules/tenancy/models.py`
  independently. The existing duplication pattern was never a deliberate design choice worth preserving —
  it was simply how the first status vocabulary happened to be wired — and since this tuple needed to move
  into real use anyway, importing it directly avoids introducing a second copy that could drift.
- **Chose a real Postgres enum for `status` over adding a `CHECK` constraint or leaving it as a plain
  string with only Python-side validation.** Every sibling status column in the codebase already uses a
  Postgres enum; leaving `SupportAccessGrant.status` as the sole exception was itself the inconsistency
  this milestone existed to fix, not a deliberate choice to preserve.
- **`get_active_grant` returns the ORM row instead of a purpose-built lightweight struct.** The route only
  needs `expires_at` off it today, but returning the row keeps the door open for a future route needing
  another field (e.g. `reason`, `requested_duration_hours`) without a second service function.

## Milestone 17 — Known Limitations

- **No countdown or proactive warning as access nears expiry** — the workspace snapshot page shows a
  static timestamp, not a live countdown or a "your access expires soon" warning. A platform admin doing
  support work would need to notice the timestamp themselves.
- **The enum migration has no backfill step because none was needed** — this is a note for future
  reviewers, not a limitation: had any row ever contained a value outside `SUPPORT_ACCESS_STATUSES`, the
  migration would have failed at the `ALTER COLUMN ... USING` cast, and it did not, confirming the worker
  has never written anything else.
- **No frontend automated tests were added for the dropdown/expiry changes** — same gap and rationale as
  every prior milestone's new UI: verified manually end-to-end via Playwright, passes lint/typecheck/build,
  but no dedicated Vitest coverage.
- **This milestone corrected two prior milestones' documentation but did not audit every other Known
  Limitation/Unresolved Risk for the same kind of staleness** — the correction here was triggered by this
  milestone's own scoping research happening to touch this specific claim, not a systematic re-verification
  pass over the full carried-over list.

## Milestone 17 — Unresolved Risks

- Carried over from Milestones 1-16 (in-memory rate limiter, no dependency/container/secret scanning in
  CI, Docker Compose still unverified end-to-end, the scoring formulas' simplicity, the inherent stakes of
  unattended action execution, the evidence permission-per-target design, the control-scoring weights, the
  cross-cutting-permission decisions, the widened-RLS-by-data-value pattern, the threat-intel
  confidence-to-severity thresholds, the HTTP-file domain-verification substitution, the widened
  `audit_logs_select` policy, the terminal-`archived` tenant status, the hardcoded MFA admin-role set, MFA
  backup/recovery codes, the workspace snapshot being the only grant-gated read, the
  RLS-silently-no-ops-without-tenant-context hazard, an active grant still gating no real platform
  capability) — none were touched this milestone and remain open.
  **[Corrected in Milestone 18: the last item in this list — "an active grant still gating no real
  platform capability" — was itself stale by the time this was written. Milestone 16 had already built a
  real grant-gated read (the workspace snapshot); this Unresolved Risks list reasserted the pre-Milestone-16
  claim without re-checking it, contradicting Milestone 16's own, more careful phrasing two sections earlier
  in this same document ("the workspace snapshot is currently the only grant-gated read" — which correctly
  acknowledged partial closure). See Milestone 18's own notes.]**
- **Other carried-over Known Limitations/Unresolved Risks have not been re-verified against current code**
  the way this milestone's "no expiry sweep" claim was — flagged explicitly, since this milestone
  demonstrated concretely that at least one such claim had been wrong for two milestones running. A future
  milestone (or an explicit ask) doing a systematic re-verification pass would have real value.
  **[Partially addressed in Milestone 18: that same re-verification instinct caught a second stale claim —
  see the correction directly above — in the very next milestone, before any systematic audit was
  attempted. Still no full audit has been done; see Milestone 18's own Known Limitations.]**

## Milestone 17 — Pending Approvals

- This Milestone 17 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps are documented rather than hidden.
- Recommend explicit review of the documentation-correction approach taken (annotating the stale claims in
  place in Milestones 15/16 rather than silently editing them) — flagging in case a different convention
  is preferred for future corrections of this kind.

## Milestone 17 — Next Action

Awaiting your review. Once you're satisfied, send **`APPROVE MILESTONE 18`** to begin the next milestone.

## Milestone 18 — Completed Work

### The breadcrumb this milestone came from
- Milestone 16's own Known Limitations named this directly: "the snapshot is read-only and narrow by
  design — members and three summary counts, not full findings/incidents/asset detail... Expanding it to
  deeper drill-down views is a natural next increment."
- Separately, before implementing, research surfaced a second stale documentation claim (beyond the
  expiry-sweep one Milestone 17 corrected): Milestone 17's own Unresolved Risks reasserted "an active grant
  still gating no real platform capability" verbatim from Milestone 15, despite Milestone 16 having already
  built a real grant-gated read in between. Corrected in place (see above) rather than silently rewritten.

### Backend
- **`findings.routes`'s route-private `_to_list_item` mapping (finding + asset → `FindingListItem`,
  including risk-score computation) promoted to `findings_service.to_finding_list_item`** — a public,
  reusable function. The tenant-facing `GET /api/findings` now calls it too, so there is exactly one place
  that maps a finding to its list representation, not two.
- **New `GET /api/platform/tenants/{tenant_id}/findings`**, gated by the same `require_support_access_grant`
  dependency as the workspace snapshot, supporting the same `severity`/`status` filters as the tenant-facing
  endpoint. Reuses `findings_service.list_findings` and the newly-promoted `to_finding_list_item` verbatim —
  no new query logic, no new risk-scoring logic.
- **Both grant-gated reads now record which view was used**, via `context={"view": "workspace_snapshot"}` /
  `context={"view": "findings", ...}` on the shared `platform.support_access_used` audit action — previously
  there was no way to tell from the audit log which of two (now more) grant-gated views a platform admin had
  actually looked at.

### Frontend (`apps/web`)
- The workspace snapshot page gained an "All findings" section listing title, severity, status, and asset
  for every finding regardless of status — the drill-down the `open_findings_total` tile alone couldn't
  provide. Deliberately shows every finding (not just open ones) for fuller support context, with an
  explanatory description so its count doesn't read as contradicting the "Open findings" tile above it (a
  wording issue caught during this milestone's own live E2E review, not by an automated check).

## Milestone 18 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| The findings drill-down requires the same active grant as the workspace snapshot | ✅ | `test_grant_gated_findings_drilldown_requires_an_active_grant` (403, `support_access_grant_required`) |
| The drill-down returns real finding data (risk score, asset name) matching the tenant-facing endpoint's shape | ✅ | `test_grant_gated_findings_drilldown_returns_real_findings`; live-verified against the demo tenant's 7 real findings |
| Severity/status filters work the same way as the tenant-facing endpoint | ✅ | Same test — filtering by the first result's severity returns only matching findings |
| Each grant-gated view is now distinguishable in the audit log | ✅ | `test_grant_gated_findings_drilldown_is_audited_with_view_context`; live-verified — `context.view` is `"workspace_snapshot"` or `"findings"` on each recorded event |
| The tenant-facing `GET /api/findings` behaves identically after the refactor | ✅ | Full `test_findings_api.py` suite (20 tests) still passes unchanged |
| Backend tests pass | ✅ | **220/220** passing (`pytest -q` in `apps/api`, up from 217 — 3 new tests), `ruff check .` clean |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 31/31 routes |

## Milestone 18 — Test Results (as actually executed in this session)

```
apps/api: pytest -q                   → 220 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 31/31 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Next.js stack, driven by headless Chromium, against the
demo tenant's 7 real seeded findings: confirmed the findings section was inaccessible before any grant
existed (same block as the workspace snapshot), requested and approved a grant through two different
platform admins as always, then confirmed the workspace page showed all 7 real finding titles (including
"Administrator account without MFA" at `critical` severity) with correct severity badges. Queried the live
platform audit log directly afterward and confirmed `context.view` correctly distinguished
`workspace_snapshot` fetches from `findings` fetches across multiple recorded events. Removed the test grant
afterward with tenant context set first, per Milestone 16's own documented lesson about that.

## Milestone 18 — Architecture Decisions (made or refined during implementation)

- **Promoted the mapping function rather than duplicating it.** `findings.routes`'s `_to_list_item` was
  route-private with no reuse story; moving it to `findings_service.to_finding_list_item` means the
  tenant-facing and platform-admin-facing findings lists can never silently drift in how they compute
  `risk_score` or shape the response, since they now call the exact same function.
- **Reused the existing `platform.support_access_used` audit action with a distinguishing `context` field**
  rather than inventing a new action name per grant-gated view. Every grant-gated read is still fundamentally
  "the grant was used" — `context.view` answers "used for what," which scales to future grant-gated views
  without growing the audit action vocabulary.
- **The findings drill-down deliberately shows every finding, not just open ones.** A support engineer
  investigating a reported issue benefits from seeing recently-remediated or accepted-risk findings too,
  not only what's currently open — the snapshot's `open_findings_total` tile already covers the "how many
  are open" question on its own.
- **Corrected the stale "gates nothing" Unresolved Risk in place rather than silently editing it**, following
  the exact convention Milestone 17 established for its own correction — consistency in how mistakes get
  documented matters as much as catching them.

## Milestone 18 — Known Limitations

- **Only findings have a drill-down; incidents and connected integrations still only have summary counts**
  on the workspace snapshot. Extending the same pattern to incidents is a natural next increment, not
  attempted here to keep this milestone scoped to the one drill-down Milestone 16 explicitly named.
- **No pagination on the findings drill-down** — for a tenant with a very large findings table, this
  returns everything in one response. The demo tenant (7 findings) and realistic small-to-mid tenant sizes
  don't currently exercise this, but it would need addressing before this view scales to a busy production
  tenant.
- **No systematic audit of the remaining carried-over Known Limitations/Unresolved Risks was performed** —
  this milestone corrected one specific stale claim it happened to encounter during its own scoping research,
  the same way Milestone 17 did, but a full pass over the entire carried-over list still hasn't been done.
- **No frontend automated tests were added for the findings section** — same gap and rationale as every
  prior milestone's new UI: verified manually end-to-end via Playwright, passes lint/typecheck/build, but no
  dedicated Vitest coverage.

## Milestone 18 — Unresolved Risks

- Carried over from Milestones 1-17 (in-memory rate limiter, no dependency/container/secret scanning in
  CI, Docker Compose still unverified end-to-end, the scoring formulas' simplicity, the inherent stakes of
  unattended action execution, the evidence permission-per-target design, the control-scoring weights, the
  cross-cutting-permission decisions, the widened-RLS-by-data-value pattern, the threat-intel
  confidence-to-severity thresholds, the HTTP-file domain-verification substitution, the widened
  `audit_logs_select` policy, the terminal-`archived` tenant status, the hardcoded MFA admin-role set, MFA
  backup/recovery codes, the RLS-silently-no-ops-without-tenant-context hazard, no pagination on findings
  reads, incidents/integrations still lacking a drill-down) — none were touched this milestone and remain
  open. (The "active grant gating no real platform capability" item has been removed from this carried-over
  list — see the correction above; two grant-gated reads exist now.)
- **A full, systematic re-verification pass over every carried-over Known Limitation/Unresolved Risk has
  still not been done** — two consecutive milestones (17 and 18) each independently caught one stale claim
  as a side effect of their own scoping research, not through a deliberate audit. The remaining list should
  not be assumed accurate without similar scrutiny.
- **No pagination on the findings drill-down** is a real scalability risk if this pattern is later applied
  to a tenant with a large findings table, flagged explicitly since it wasn't addressed this milestone.

## Milestone 18 — Pending Approvals

- This Milestone 18 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps are documented rather than hidden.
- Recommend explicit review of the decision to defer pagination and the incidents/integrations drill-down
  to a future milestone rather than building all three grant-gated drill-downs at once.

## Milestone 18 — Next Action

Awaiting your review. Once you're satisfied, send **`APPROVE MILESTONE 19`** to begin the next milestone.

## Milestone 19 — Completed Work

### The breadcrumb this milestone came from
- Milestone 18's own Known Limitations named this directly: "Only findings have a drill-down; incidents
  and connected integrations still only have summary counts on the workspace snapshot. Extending the same
  pattern to incidents is a natural next increment." This milestone builds exactly that — the second of the
  two summary-only tiles Milestone 16 originally flagged.
- Separately: while reviewing this document to append Milestone 19's sections, a stray duplicate line was
  found at the very end of the file — a leftover "Awaiting your review... APPROVE MILESTONE 17" line that
  had never been cleaned up when Milestone 18's content was appended. Removed as part of this milestone's
  documentation update; not a claim about functionality, just a file-hygiene fix worth noting honestly
  rather than silently.

### Backend
- **`incidents.routes`'s route-private `_to_list_item` mapping promoted to
  `incidents_service.to_incident_list_item`** — the exact same refactor Milestone 18 applied to findings.
  The tenant-facing `GET /api/incidents` now calls it too.
- **New `GET /api/platform/tenants/{tenant_id}/incidents`**, gated by `require_support_access_grant`,
  supporting the same `status`/`severity` filters as the tenant-facing endpoint. Reuses
  `incidents_service.list_incidents` and `to_incident_list_item` verbatim.
- **Tagged with `context={"view": "incidents", ...}`** on the shared `platform.support_access_used` audit
  action, extending the distinguishing pattern Milestone 18 introduced to a third grant-gated view.

### Frontend (`apps/web`)
- The workspace snapshot page gained an "Incidents" section listing title, severity, and status for every
  incident, fetched from the new endpoint — mirroring the findings section's structure and using the same
  severity/status badge conventions as the tenant-facing `/incidents` page.

## Milestone 19 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| The incidents drill-down requires the same active grant as the other grant-gated views | ✅ | `test_grant_gated_incidents_drilldown_requires_an_active_grant` (403, `support_access_grant_required`) |
| The drill-down returns real incident data matching the tenant-facing endpoint's shape | ✅ | `test_grant_gated_incidents_drilldown_returns_real_incidents`; live-verified against a real declared incident on the demo tenant |
| Severity filtering works the same way as the tenant-facing endpoint | ✅ | Same test — filtering by a non-matching severity returns an empty list |
| The incidents view is distinguishable from the other two grant-gated views in the audit log | ✅ | `test_grant_gated_incidents_drilldown_is_audited_with_view_context`; live-verified — `context.view` values `workspace_snapshot`, `findings`, and `incidents` all observed across recorded events in one session |
| The tenant-facing `GET /api/incidents` behaves identically after the refactor | ✅ | Full `test_incidents_api.py` + `test_incidents_engine.py` suites (18 tests) still pass unchanged |
| Backend tests pass | ✅ | **223/223** passing (`pytest -q` in `apps/api`, up from 220 — 3 new tests), `ruff check .` clean |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 31/31 routes |

## Milestone 19 — Test Results (as actually executed in this session)

```
apps/api: pytest -q                   → 223 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 31/31 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Next.js stack, driven by headless Chromium: declared a
real incident ("M19 E2E verification incident", `high` severity) against the demo tenant as its owner,
confirmed the incidents section was inaccessible before any grant existed, requested and approved a grant
through two different platform admins as always, then confirmed the workspace page showed the real
declared incident with correct severity and status badges. Queried the live platform audit log afterward
and confirmed all three grant-gated views (`workspace_snapshot`, `findings`, `incidents`) were each
distinctly represented via `context.view` across the session's recorded events. Removed the test grant and
the test incident afterward, with tenant context set first.

This session's backend verification runs were also interrupted twice by the local Postgres/Redis services
going down mid-session (unrelated to any code change — confirmed via `pg_isready`/`redis-cli ping` both
failing, then both services restarting cleanly via `service postgresql start` / `service redis-server
start`). Noted here for the record since it caused two rounds of spurious `alembic upgrade head` test
failures that had nothing to do with this milestone's actual changes.

## Milestone 19 — Architecture Decisions (made or refined during implementation)

- **Extended the exact Milestone 18 pattern rather than inventing a new one** — same dependency
  (`require_support_access_grant`), same promoted-mapping-function shape, same audit `context.view`
  convention, same frontend card structure. Consistency across the three grant-gated views matters more
  than any per-view optimization would have.
- **No new schema, no new migration** — this is the second consecutive milestone (after Milestone 18) that
  is a pure read composition over existing tables plus route wiring, the same shape Milestone 8's
  `modules.reporting` and Milestone 18's findings drill-down both took.

## Milestone 19 — Known Limitations

- **Connected integrations still has no drill-down** — the third and last summary-only tile on the
  workspace snapshot. A natural next increment, not attempted here to keep this milestone scoped to the one
  drill-down Milestone 18 explicitly named next.
- **No pagination on the incidents drill-down**, the same gap Milestone 18 flagged for findings — not
  addressed here either, for the same reason (small demo/realistic tenant sizes don't currently exercise
  it).
- **No systematic audit of the remaining carried-over Known Limitations/Unresolved Risks was performed** —
  the third consecutive milestone to note this without actually doing the full pass.
- **No frontend automated tests were added for the incidents section** — same gap and rationale as every
  prior milestone's new UI.

## Milestone 19 — Unresolved Risks

- Carried over from Milestones 1-18 (in-memory rate limiter, no dependency/container/secret scanning in
  CI, Docker Compose still unverified end-to-end, the scoring formulas' simplicity, the inherent stakes of
  unattended action execution, the evidence permission-per-target design, the control-scoring weights, the
  cross-cutting-permission decisions, the widened-RLS-by-data-value pattern, the threat-intel
  confidence-to-severity thresholds, the HTTP-file domain-verification substitution, the widened
  `audit_logs_select` policy, the terminal-`archived` tenant status, the hardcoded MFA admin-role set, MFA
  backup/recovery codes, the RLS-silently-no-ops-without-tenant-context hazard, no pagination on
  findings/incidents reads, connected integrations still lacking a drill-down) — none were touched this
  milestone and remain open.
- **A full, systematic re-verification pass over every carried-over Known Limitation/Unresolved Risk has
  still not been done** — three consecutive milestones (17, 18, and 19) have each independently caught one
  stale documentation issue as a side effect of other work (a factual claim, a factual claim, and a stray
  duplicate line, respectively), not through a deliberate audit. This pattern itself is now worth treating
  as a signal that a dedicated documentation-audit milestone would have real value.
- **No pagination on findings or incidents drill-downs** remains a real scalability risk if either pattern
  is later applied to a tenant with a large table.

## Milestone 19 — Pending Approvals

- This Milestone 19 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps are documented rather than hidden.
- Recommend explicit review of the decision to defer the connected-integrations drill-down and pagination
  to a future milestone rather than building everything at once, and of the observation (repeated three
  milestones running now) that a dedicated documentation-audit milestone may be worth prioritizing over
  another incremental feature.

## Milestone 19 — Next Action

Awaiting your review. Once you're satisfied, send **`APPROVE MILESTONE 20`** to begin the next milestone.

## Milestone 20 — Completed Work

### The breadcrumb this milestone came from
- Milestone 19's own Known Limitations named this directly: "Connected integrations still has no
  drill-down — the third and last summary-only tile on the workspace snapshot." This milestone builds
  exactly that, completing the trilogy of grant-gated drill-downs Milestone 16's workspace snapshot
  originally left as summary-only tiles.

### Backend
- **`integrations.routes`'s route-private `_to_tenant_integration_read` mapping promoted to
  `integrations_service.to_tenant_integration_read`** — the same refactor Milestone 18 applied to findings
  and Milestone 19 applied to incidents. The tenant-facing `GET /api/integrations`,
  `POST /api/integrations`, and `POST /api/integrations/{id}/disconnect` all now call it.
- **New `GET /api/platform/tenants/{tenant_id}/integrations`**, gated by `require_support_access_grant`.
  Reuses `integrations_service.list_tenant_integrations` and `to_tenant_integration_read` verbatim — no
  new query, no new mapping logic.
- **Tagged with `context={"view": "integrations"}`** on the shared `platform.support_access_used` audit
  action, extending the distinguishing pattern to a fourth grant-gated view (workspace snapshot, findings,
  incidents, integrations).

### Frontend (`apps/web`)
- The workspace snapshot page gained an "Integrations" section listing provider, label, status, and
  last-synced time for every connected integration, fetched from the new endpoint — completing the
  three-way drill-down (findings, incidents, integrations) alongside the summary tiles at the top of the
  page.

## Milestone 20 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| The integrations drill-down requires the same active grant as the other grant-gated views | ✅ | `test_grant_gated_integrations_drilldown_requires_an_active_grant` (403, `support_access_grant_required`) |
| The drill-down returns real integration data matching the tenant-facing endpoint's shape | ✅ | `test_grant_gated_integrations_drilldown_returns_real_integrations`; live-verified against the demo tenant's 5 real connected integrations |
| The integrations view is distinguishable from the other three grant-gated views in the audit log | ✅ | `test_grant_gated_integrations_drilldown_is_audited_with_view_context`; live-verified — `context.view` values `workspace_snapshot`, `findings`, `incidents`, and `integrations` all observed across recorded events in one session |
| The tenant-facing integrations endpoints behave identically after the refactor | ✅ | Full `test_integrations_and_assets.py` suite (8 tests) still passes unchanged |
| All three drill-downs (findings, incidents, integrations) render together on one workspace snapshot page | ✅ | Live-verified via full-page screenshot showing all three sections with real demo-tenant data simultaneously |
| Backend tests pass | ✅ | **226/226** passing (`pytest -q` in `apps/api`, up from 223 — 3 new tests), `ruff check .` clean |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 31/31 routes |

## Milestone 20 — Test Results (as actually executed in this session)

```
apps/api: pytest -q                   → 226 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 31/31 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Next.js stack, driven by headless Chromium: confirmed the
integrations section was inaccessible before any grant existed, requested and approved a grant through two
different platform admins as always, then confirmed the workspace page showed all 5 of the demo tenant's
real connected integrations (Simulated Identity Provider, Endpoint Platform, Cloud Provider, Backup
Platform, Threat Intelligence Feed) with correct status badges and last-synced timestamps — alongside the
findings and incidents sections from the prior two milestones, all rendering together on one page. Queried
the live platform audit log afterward and confirmed all four grant-gated views were each distinctly
represented via `context.view`. Removed the test grant afterward, with tenant context set first.

This session was also interrupted once by a full container restart mid-verification (background processes
lost, working-tree changes preserved) and once more by Postgres/Redis going down (same as Milestone 19) —
both required restarting local services (`service postgresql start` / `service redis-server start`) before
verification could resume. Neither was related to any code change; noted here for the record.

## Milestone 20 — Architecture Decisions (made or refined during implementation)

- **Completed the trilogy using the exact same pattern for the third time**, rather than varying the
  approach — same dependency, same promoted-mapping-function shape, same audit `context.view` convention,
  same frontend card structure. By the third repetition, this is now an established, low-risk pattern for
  adding a grant-gated read, not something requiring fresh design decisions each time.
- **No new schema, no new migration** — the third consecutive milestone that is a pure read composition
  over existing tables plus route wiring.

## Milestone 20 — Known Limitations

- **All three drill-downs still have no pagination**, the same gap flagged in Milestones 18 and 19 — not
  addressed here either. With the trilogy now complete, this is the most concrete remaining gap across all
  three grant-gated reads and would be a reasonable, well-scoped next increment.
- **No systematic audit of the remaining carried-over Known Limitations/Unresolved Risks was performed** —
  the fourth consecutive milestone to note this without doing the full pass. With the drill-down trilogy
  now complete and no further "natural next increment" obviously named, the next milestone may be a better
  point to prioritize this over another incremental feature.
- **No frontend automated tests were added for the integrations section** — same gap and rationale as every
  prior milestone's new UI.

## Milestone 20 — Unresolved Risks

- Carried over from Milestones 1-19 (in-memory rate limiter, no dependency/container/secret scanning in
  CI, Docker Compose still unverified end-to-end, the scoring formulas' simplicity, the inherent stakes of
  unattended action execution, the evidence permission-per-target design, the control-scoring weights, the
  cross-cutting-permission decisions, the widened-RLS-by-data-value pattern, the threat-intel
  confidence-to-severity thresholds, the HTTP-file domain-verification substitution, the widened
  `audit_logs_select` policy, the terminal-`archived` tenant status, the hardcoded MFA admin-role set, MFA
  backup/recovery codes, the RLS-silently-no-ops-without-tenant-context hazard, no pagination on any of the
  three grant-gated drill-downs) — none were touched this milestone and remain open.
- **A full, systematic re-verification pass over every carried-over Known Limitation/Unresolved Risk has
  still not been done**, now flagged for a fourth consecutive milestone. With the drill-down trilogy
  complete, this is a genuinely strong candidate for Milestone 21's scope rather than continuing to defer
  it — explicitly flagged for your review.
- **No pagination across all three grant-gated drill-downs** is the clearest concrete remaining gap in this
  specific feature area, now that all three exist.

## Milestone 20 — Pending Approvals

- This Milestone 20 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps are documented rather than hidden.
- Recommend explicit review of two competing candidates for Milestone 21: (a) adding pagination to the now-
  complete drill-down trilogy, or (b) the dedicated documentation-audit pass flagged for four consecutive
  milestones now. Both are legitimate; your preference would help focus the next milestone rather than
  another judgment call made independently.

## Milestone 20 — Next Action

Awaiting your review. Once you're satisfied, send **`APPROVE MILESTONE 21`** to begin the next milestone.

## Milestone 21: Pagination for the Grant-Gated Drill-Down Trilogy

**Scope chosen by user instruction "Pick one by default"** — after Milestone 20 flagged two competing
candidates (pagination vs. a documentation-audit pass) and I stated pagination as my own default absent a
preference, the user approved that default directly. This closes the "no pagination on the drill-down" gap
flagged in Milestones 18, 19, and 20.

### Backend (`apps/api`)
- **`findings_service.list_findings`, `incidents_service.list_incidents`, and
  `integrations_service.list_tenant_integrations`** each gained opt-in `limit: int | None = None` /
  `offset: int = 0` parameters. `limit is None` (the default) preserves each function's exact prior
  behaviour — every tenant-facing route (`GET /api/findings`, `GET /api/incidents`, `GET /api/integrations`)
  calls these functions without the new parameters and is byte-for-byte unaffected. Only
  `modules.platform_admin`'s three grant-gated drill-down routes pass them.
- **`modules.platform_admin.routes`**: `get_tenant_findings_for_support`, `get_tenant_incidents_for_support`,
  and `get_tenant_integrations_for_support` each gained
  `limit: int = Query(default=50, ge=1, le=200)` / `offset: int = Query(default=0, ge=0)`, mirroring
  `list_platform_audit_logs`'s exact style established in Milestone 12, and pass them straight through to
  the corresponding service call.
- **A real ordering bug was found and fixed during live E2E verification, not by inspection.** All three
  list queries used `ORDER BY <single timestamp column> DESC` with no tie-breaker. Postgres does not
  guarantee stable `LIMIT`/`OFFSET` windowing without a deterministic `ORDER BY`, and the demo tenant's
  findings — several correlated in the same run and sharing an identical `last_observed_at` — proved this
  live: paginated pages did not line up with slices of the unpaginated list for tied rows. Fixed by adding
  `Finding.id` / `Incident.id` as a secondary sort key in `list_findings` and `list_incidents`.
  `list_tenant_integrations` already needed an `ORDER BY` added from scratch (it had none before, since it
  always returned every row) and was given `created_at.desc()` directly — no ties were observed there live,
  but the same class of risk exists if two integrations were ever connected in the same transaction, so it's
  worth knowing this endpoint doesn't yet have the same explicit tie-breaker as the other two. Not fixed in
  this milestone since it wasn't observed to actually manifest; flagged below as a Known Limitation.
- Explicit `limit=0` and `limit=500` (over the `le=200` cap) both correctly return `422` — verified live
  against the running server, not just via the backend test suite.

### Frontend (`apps/web`)
- The three drill-down `useQuery` calls on the tenant workspace snapshot page (findings, incidents,
  integrations) now pass an explicit `limit: "100"` query parameter, mirroring the exact minimal pattern
  the platform audit-logs page already established in Milestone 12 (explicit limit, no pager UI, no "load
  more" control). This is a page-size cap, not a scrolling/pagination UI — matching the existing precedent
  rather than inventing a new one.

## Milestone 21 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| Tenant-facing findings/incidents/integrations endpoints are unaffected by the pagination change | ✅ | Full `test_findings_api.py`, `test_findings_engine.py`, `test_incidents_api.py`, `test_incidents_engine.py`, `test_integrations_and_assets.py` suites (74 tests) pass unchanged |
| The findings drill-down respects `limit`/`offset` | ✅ | `test_grant_gated_findings_drilldown_pagination`; live-verified against the demo tenant's 7 real findings across three separate `limit=3` pages, and confirmed `limit=0` returns `422` |
| The incidents drill-down respects `limit`/`offset`, ordered newest-declared-first | ✅ | `test_grant_gated_incidents_drilldown_pagination` (3 declared incidents, `limit=2`/`offset=2` pages) |
| The integrations drill-down respects `limit`/`offset`, ordered newest-connected-first | ✅ | `test_grant_gated_integrations_drilldown_pagination` (3 connected integrations, `limit=2`/`offset=2` pages); live-verified against the demo tenant's 5 real integrations |
| Pagination windows are internally consistent (no duplicate/missing rows across pages for tied timestamps) | ✅ | Live-verified directly against the demo tenant's findings (several sharing an identical `last_observed_at`) before and after the `Finding.id`/`Incident.id` tie-breaker fix — confirmed the bug, then confirmed the fix made paginated windows match exact slices of the unpaginated list |
| Out-of-range `limit` values are rejected | ✅ | `limit=0` and `limit=500` both return `422` (FastAPI `Query(ge=1, le=200)` validation), verified live and in the automated pagination tests |
| Backend tests pass | ✅ | **229/229** passing (`pytest -q` in `apps/api`, up from 226 — 3 new pagination tests), `ruff check .` clean |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 31/31 routes |

## Milestone 21 — Test Results (as actually executed in this session)

```
apps/api: pytest -q                   → 229 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 31/31 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Next.js stack, driven by headless Chromium and direct API
calls against the running server (using the demo tenant "Northstar Advisory Demo" — 7 real findings, 5 real
connected integrations):

1. Requested and approved a real support access grant through two distinct platform admins, as always.
2. Queried the findings drill-down directly (`curl`) with `limit=3&offset=0`, `limit=3&offset=3`, and
   `limit=3&offset=6`, and separately queried the full unpaginated list. **Before the tie-breaker fix**,
   the three-page ordering did not match slices of the full list — a real, live-caught bug caused by
   several findings sharing an identical `last_observed_at` timestamp with no secondary sort key. Fixed
   `list_findings`/`list_incidents` to add `.id` as a tie-breaker, restarted `uvicorn`, and re-ran the exact
   same three queries: the three pages now concatenate to exactly the full unpaginated list, in the same
   order, with no gaps or duplicates.
3. Ran the same limit=2/offset=0 and limit=2/offset=2 verification against the integrations drill-down
   (5 real connected integrations) — pages lined up correctly without needing a fix, since no two
   integrations in this tenant share a `created_at` timestamp.
4. Confirmed `limit=0` and `limit=500` both return `422` against the live server.
5. Logged in as the platform support engineer in a real headless browser, navigated directly to the tenant
   workspace snapshot page, and confirmed via captured network responses that all three drill-down requests
   now include `limit=100` and return `200`, with the page rendering all 7 findings, 0 incidents, and 5
   integrations correctly (screenshot captured).
6. Revoked the test grant afterward, with tenant context set first.

## Milestone 21 — Architecture Decisions (made or refined during implementation)

- **Pagination is strictly opt-in at the service-function level** (`limit: int | None = None`), not a
  required parameter — a deliberate low-risk choice so the tenant-facing routes, which never pass `limit`,
  keep their exact prior behaviour with zero regression risk. Only the platform-admin drill-downs, the
  specific gap that was actually flagged, changed behaviour.
- **The frontend uses a fixed `limit=100` page-size cap with no pager UI**, mirroring the audit-logs page's
  existing precedent exactly rather than inventing a scrolling or "load more" pattern for this milestone.
  This is consistent with the platform console's existing read-only, single-page philosophy.
- **The integrations-ordering tie-breaker gap was deliberately left unfixed**, unlike findings/incidents,
  since it was not observed to actually manifest live (no two integrations in the demo tenant share a
  `created_at`) and speculative hardening beyond what was actually flagged or observed was judged out of
  scope for this milestone. Documented explicitly below rather than silently left inconsistent.

## Milestone 21 — Known Limitations

- **`list_tenant_integrations` has no explicit tie-breaker on `created_at`**, unlike `list_findings` and
  `list_incidents`, which now both sort by `.id` as a secondary key. The risk is the same class of bug this
  milestone found and fixed live for findings — it just wasn't observed to manifest for integrations in the
  demo tenant. Two integrations connected in the same transaction (same `created_at` to the microsecond)
  would be exposed to it. A one-line fix (`.order_by(TenantIntegration.created_at.desc(), TenantIntegration.id)`)
  if and when this is prioritized.
- **No pager UI exists on the frontend** — the three drill-downs simply request up to 100 rows and show
  them all. A tenant with more than 100 findings, incidents, or integrations would not have full visibility
  in the platform support view (though its own tenant-facing pages remain unpaginated and unaffected). Not
  observed in current demo data (max real count seen: 7 findings) but a genuine gap for any tenant that
  grows past 100 in one of these tables.
- **No systematic audit of the remaining carried-over Known Limitations/Unresolved Risks was performed** —
  now the fifth consecutive milestone to note this without doing the full pass, since a concrete, well-
  scoped alternative (pagination) was chosen instead by explicit user instruction this time. This remains
  the strongest candidate for a dedicated Milestone 22.
- **No frontend automated tests were added** for the `limit` query-parameter change — same gap and
  rationale as every prior milestone's UI changes to this page.

## Milestone 21 — Unresolved Risks

- Carried over from Milestones 1-20 (in-memory rate limiter, no dependency/container/secret scanning in CI,
  Docker Compose still unverified end-to-end, the scoring formulas' simplicity, the inherent stakes of
  unattended action execution, the evidence permission-per-target design, the control-scoring weights, the
  cross-cutting-permission decisions, the widened-RLS-by-data-value pattern, the threat-intel
  confidence-to-severity thresholds, the HTTP-file domain-verification substitution, the widened
  `audit_logs_select` policy, the terminal-`archived` tenant status, the hardcoded MFA admin-role set, MFA
  backup/recovery codes, the RLS-silently-no-ops-without-tenant-context hazard) — none were touched this
  milestone and remain open.
- **`list_tenant_integrations`'s missing `.id` tie-breaker** (new this milestone — see Known Limitations
  above) is a small, understood, currently-latent risk.
- **No pager UI beyond a 100-row cap on the three grant-gated drill-downs** (new this milestone — see Known
  Limitations above) is a real gap for any tenant whose data grows past that cap.
- **A full, systematic re-verification pass over every carried-over Known Limitation/Unresolved Risk has
  still not been done**, now flagged for a fifth consecutive milestone. This is a genuinely strong
  candidate for Milestone 22's scope.

## Milestone 21 — Pending Approvals

- This Milestone 21 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps (including the live-caught-and-fixed
  ordering bug and the one deliberately-left tie-breaker gap) are documented rather than hidden.
- Recommend the dedicated documentation-audit pass, flagged for five consecutive milestones now, as the
  strongest candidate for Milestone 22 — the drill-down trilogy and its pagination are both complete, and no
  other concrete, in-repo-flagged feature gap remains as obviously named as this one.

## Milestone 21 — Next Action

Awaiting your review. Once you're satisfied, send **`APPROVE MILESTONE 22`** to begin the next milestone.

## Milestone 22: Documentation-Audit Pass

**Scope inferred from breadcrumb, not user instruction** — the user's "Continue" after Milestone 21's
completion was interpreted as approval to proceed with the milestone I had explicitly named as the strongest
candidate in Milestone 21's own Pending Approvals: a systematic re-verification pass over every carried-over
Known Limitation and Unresolved Risk, flagged for five consecutive milestones (18-21) without ever being
done.

### What this milestone actually did
Went through the full accumulated risk/limitation history in this document — both the parenthetical
"carried over" shorthand list that's been rolling forward since Milestone 12, and the older,
milestone-specific Known Limitations sections from Milestones 1-11 that predate that rolling list — and
checked each concrete, checkable claim against the current state of the codebase (not just re-read the
prose). Design-decision-style items ("the scoring formulas' simplicity", "the control-scoring weights", etc.)
were not re-litigated — those are accepted tradeoffs, not factual claims that can go stale. The audit focused
on claims of the form "X is not yet built" / "X has zero callers" / "X is not enforced", which are exactly
the kind of statement later milestones can silently invalidate without anyone going back to fix the sentence
that made the original claim.

**Confirmed still accurate (checked against current code, not just assumed):**
- In-memory rate limiter (`core/middleware.py`'s `InMemorySlidingWindowLimiter`) — unchanged.
- No dependency/container/secret scanning in `.github/workflows/ci.yml` — unchanged (ruff, migrations,
  pytest, eslint, tsc, vitest, build, and the security-contracts sync check are the only jobs).
- No MFA backup/recovery codes — confirmed no `recovery_code`/`backup_code` concept exists anywhere in
  `modules.identity`.
- The hardcoded `ADMIN_ROLE_NAMES` frozenset (`tenant_owner`, `security_administrator`) in
  `modules.tenancy.service` — unchanged since Milestone 14, no tenant-configurable equivalent added.
- The terminal `archived` tenant status — `_VALID_TENANT_STATUS_TRANSITIONS["archived"]` is still an empty
  frozenset; no reactivation path exists.
- The HTTP-file-only domain verification substitution in `modules.attack_surface` (`_VERIFICATION_METHOD =
  "http_file"`) — no DNS TXT alternative was ever added.
- The widened `audit_logs_select` RLS policy (`tenant_id = app_current_tenant_id() OR
  app_is_platform_admin()`) — matches the migration exactly as originally documented.
- Asset dedup is still keyed purely on `(tenant_id, identifier_type, identifier_value)` — no cross-provider
  identity resolution was ever added to `modules.assets.ingestion`.
- Threat-intel matches still don't trigger playbook automation — `run_threat_intel_correlation` still has no
  `actionable_finding_ids` concept.
- Object storage and real email delivery are still simulated — `email_dispatch_simulated` structured-log
  line and unused `object_storage_*` config settings both confirmed unchanged.

**Found stale and corrected in place** (using the same `**[Resolved in Milestone N: ...]**` annotation
convention Milestones 17 and 18 established, never silently rewriting the original claim):
- **Milestone 1's "MFA is schema-only... no route enforces MFA setup or challenge yet"** — fully resolved by
  Milestones 13 (real enrollment/login-challenge/step-up routes) and 14 (actual enforcement), but the
  original M1 sentence was never annotated. This claim predates the "carried over" rolling list entirely
  (it lived only in Milestone 1's own Known Limitations, never in the parenthetical shorthand), which is
  likely why it was never swept up by any later correction pass.
- **Milestone 13's "`require_mfa_for_admins` and `require_step_up_for_disruptive_actions`... neither is
  actually enforced yet"** — resolved one milestone later, by Milestone 14, but never annotated at the
  source. Same root cause as the Milestone 1 claim above: it lived in a milestone-specific section, not the
  rolling carried-over list, so it fell outside the scope of Milestones 17/18's prior correction passes
  (which only ever corrected claims already inside that rolling list).

**A real, small bug found and fixed rather than just documented:**
- `list_tenant_integrations` was the one place Milestone 21 deliberately left an ordering tie-breaker gap
  (documented honestly as a Known Limitation at the time, since it hadn't been observed to manifest). This
  audit closed it: added `TenantIntegration.id` as the same secondary sort key `list_findings`/
  `list_incidents` already got in Milestone 21, for consistency and to remove the latent risk rather than
  continue carrying it forward.

### Backend (`apps/api`)
- `modules.integrations.service.list_tenant_integrations`: `ORDER BY created_at DESC` gained `, id` as a
  tie-breaker — one line, same fix class as Milestone 21's live-caught findings/incidents bug, applied here
  pre-emptively rather than waiting for it to actually manifest.

## Milestone 22 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| Every concrete (non-design-tradeoff) carried-over Known Limitation/Unresolved Risk claim was checked against current code | ✅ | See the itemized "Confirmed still accurate" list above — each backed by a direct code check, not assumption |
| Stale claims found are corrected in place, not silently rewritten | ✅ | Two `[Resolved in Milestone N: ...]` annotations added, preserving the original text |
| `list_tenant_integrations`'s tie-breaker gap is closed | ✅ | `TenantIntegration.id` added as a secondary sort key |
| No regressions from the tie-breaker addition | ✅ | Full `pytest -q` suite (229/229) passes unchanged |
| Backend tests pass | ✅ | **229/229** passing (`pytest -q` in `apps/api`, unchanged count — this milestone added no new tests, since the fix is already covered by Milestone 21's pagination/ordering tests exercising `list_tenant_integrations`), `ruff check .` clean |

## Milestone 22 — Test Results (as actually executed in this session)

```
apps/api: pytest -q                   → 229 passed
apps/api: ruff check .                → All checks passed
```

No frontend or new backend behavior was introduced this milestone (the `.id` tie-breaker is an ordering
implementation detail with no schema, route, or response-shape change), so the full frontend
lint/typecheck/vitest/build suite and a live Playwright E2E pass were judged unnecessary — nothing exists for
either to exercise that Milestone 21's own live verification and automated pagination tests don't already
cover. This is a narrower verification scope than every prior milestone, stated explicitly rather than
silently reused from Milestone 21's log.

This session was interrupted once more by Postgres/Redis going down (the same recurring, code-unrelated
environment issue noted in Milestones 19-21) — fixed via `service postgresql start` / `service
redis-server start` before the test suite could run.

## Milestone 22 — Architecture Decisions (made or refined during implementation)

- **The audit's scope was claims, not design decisions.** Judgment calls documented as Unresolved Risks
  (scoring weights, cross-cutting permission choices, RLS widening tradeoffs, TTL/threshold values) are
  intentional and don't "go stale" the way a factual "X doesn't exist yet" statement can — re-litigating them
  wasn't this milestone's job, and doing so would have diluted the actual finding (two claims that were
  simply wrong by the time of reading).
- **Root-caused *why* two stale claims survived five milestones of "carried over" tracking**: both lived in
  milestone-specific Known Limitations sections that predate or sit outside the rolling parenthetical list
  Milestones 12+ use. The rolling list mechanism works correctly for what it tracks; it simply never tracked
  these two. Noted explicitly so a future audit knows to check milestone-specific sections too, not just the
  rolling list.
- **Fixed the `list_tenant_integrations` tie-breaker rather than just noting it was still open** — it was
  already fully scoped (a one-line, low-risk change explicitly named in Milestone 21's own docs), so treating
  it as a "found stale claim" that must only be documented rather than fixed would have been an arbitrary
  distinction with no real benefit over just closing it.

## Milestone 22 — Known Limitations

- **The audit was not exhaustive over every word of every prior milestone's prose** — it targeted claims
  matching an identifiable pattern ("not yet", "zero callers", "not enforced", "does not support") via
  targeted search, cross-checked against code. A stale claim phrased in a way that didn't match any of these
  patterns could theoretically have been missed.
- **No frontend automated tests were added** — this milestone touched no frontend code.

## Milestone 22 — Unresolved Risks

- Carried over from Milestones 1-21, confirmed still accurate this milestone (in-memory rate limiter, no
  dependency/container/secret scanning in CI, Docker Compose still unverified end-to-end, the scoring
  formulas' simplicity, the inherent stakes of unattended action execution, the evidence
  permission-per-target design, the control-scoring weights, the cross-cutting-permission decisions, the
  widened-RLS-by-data-value pattern, the threat-intel confidence-to-severity thresholds, the HTTP-file
  domain-verification substitution, the terminal-`archived` tenant status, the hardcoded MFA admin-role set,
  MFA backup/recovery codes, the RLS-silently-no-ops-without-tenant-context hazard, no pager UI beyond a
  100-row cap on the three grant-gated drill-downs) — none were touched this milestone and remain open by
  design or by explicit prior deferral.
- **`list_tenant_integrations`'s tie-breaker gap is now closed**, removed from this list.
- **No further concrete, in-repo-flagged feature gap is currently named** anywhere in this document. Unlike
  every milestone from 15 through 21, which each had an obvious next breadcrumb (second-approver flow → MFA
  → enforcement → workspace snapshot → expiry exposure → findings drill-down → incidents drill-down →
  integrations drill-down → pagination → this audit), Milestone 23 has no equally obvious candidate. Your
  direction would be genuinely valuable here rather than another default judgment call.

## Milestone 22 — Pending Approvals

- This Milestone 22 implementation is ready for your review. Nothing further is pending my side — the audit
  is complete, the two stale claims found are corrected in place, the one small live risk is closed, tests
  pass, and the audit's own limitations (not exhaustive, targeted-pattern-based) are stated rather than
  implied to be a complete guarantee.
- No default scope is proposed for Milestone 23 — see the note in Unresolved Risks above. Please advise on
  direction (e.g. a specific module to deepen, hardening work like the rate limiter or CI scanning, or a new
  feature area).

## Milestone 22 — Next Action

Awaiting your direction on Milestone 23 — there is no obvious next breadcrumb this time, so a specific
instruction would help more than another inferred default.

## Milestone 23: Redis-Backed Rate Limiter

**Scope chosen without a specific user instruction** — the user's "Continue" arrived without picking from
the candidates Milestone 22 listed (rate limiter, CI scanning, MFA backup codes, Docker Compose
verification, drill-down pager UI). Consistent with this session's established rhythm of proceeding on a
stated default rather than blocking, and since no single fallback had been pre-committed this time, the
most concretely-scoped candidate was chosen: `InMemorySlidingWindowLimiter`'s own docstring, unchanged since
Milestone 1, named its own replacement outright — "Multi-instance production deployments must back this
with Redis (INCR + EXPIRE per window) — the interface below (`check`) is the seam for that swap." This
closes the oldest-standing item on the Unresolved Risks list, carried since Milestone 1 across all 22 prior
milestones.

### Backend (`apps/api`)
- **`core.middleware.InMemorySlidingWindowLimiter` replaced outright by `RedisRateLimiter`**, not kept
  alongside it — nothing else in the codebase referenced the old class (confirmed by grep before deleting
  it), so there was no reason to leave dead code behind.
- **Algorithm changed from a true sliding window to a fixed window (`INCR` + `EXPIRE`)** — a deliberate
  simplification, not an oversight: it's the exact technique the original docstring named, needs no Lua
  scripting or sorted-set bookkeeping, and is the standard building block for this in Redis. The tradeoff
  (a client can get up to `2 × limit` requests through across a window boundary) is documented in the new
  class's own docstring and called out below rather than left implicit.
- **Reused the existing `redis` dependency and `settings.redis_url`** — already present for Celery's
  broker/backend, so no new dependency was added. The rate limiter uses `redis.asyncio.Redis.from_url(...)`
  directly rather than going through Celery at all; the two are unrelated Redis clients against the same
  instance.
- **Keys are prefixed `ratelimit:`** so a test-only `reset_all()` (scan-and-delete by that prefix) can clear
  limiter state between tests without a blanket `FLUSHDB` that would also wipe Celery's broker/backend data
  sharing the same Redis instance.
- **All three call sites in `modules.identity.routes`** (`login`'s per-IP and per-account checks,
  `forgot_password`'s per-email check) changed from `login_rate_limiter.check(...)` to
  `await login_rate_limiter.check(...)`, since the Redis-backed `check` is necessarily async where the
  in-memory one wasn't.
- **`tests/conftest.py`'s `_reset_rate_limiter` fixture** became an async `pytest_asyncio.fixture`, calling
  `await login_rate_limiter.reset_all()` instead of clearing an in-memory dict directly.

## Milestone 23 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| Rate limiting still works for a single instance (unchanged external behavior) | ✅ | `test_rate_limiting_on_login` (existing test, unmodified) still passes — 15 failed logins still trip a 429 |
| Rate-limit state is now shared across separate processes, not per-process | ✅ | New `test_rate_limiter_state_is_shared_across_separate_processes` (two independent `RedisRateLimiter` instances backed by the same Redis, proven to share one counter); live-verified against two real `uvicorn` processes on ports 8000/8001 |
| A legitimate login is unaffected once outside the rate-limit window | ✅ | Live-verified: the demo tenant owner logged in successfully (`200`, valid `csrf_token`) immediately after the limiter test cleared its key |
| Redis keys use real TTLs matching the configured window | ✅ | Live-verified via `redis-cli keys "ratelimit:*"` / `ttl` — `ratelimit:login-ip:127.0.0.1` observed with a live-counting TTL under 60s |
| No regressions elsewhere | ✅ | Full `pytest -q` suite (230/230, up from 229 — one new test) passes |
| Backend tests pass | ✅ | **230/230** passing, `ruff check .` clean |

## Milestone 23 — Test Results (as actually executed in this session)

```
apps/api: pytest -q                   → 230 passed
apps/api: ruff check .                → All checks passed
```

No frontend code changed this milestone (the rate limiter is entirely server-side, with no schema or
response-shape change visible to any client), so the frontend lint/typecheck/vitest/build suite was judged
unnecessary — stated explicitly rather than silently skipped.

Manual, real end-to-end verification performed against a live Postgres/Redis stack: started two independent
`uvicorn` processes on ports 8000 and 8001 (standing in for two horizontally-scaled API instances — they
share nothing in Python process memory), both pointed at the same `REDIS_URL`. Sent repeated failed-login
requests split across both ports for the same client IP: instance A handled 6 requests, then instance B
handled 2 more (8 combined) before hitting a small pre-existing count already in the bucket from an earlier
check, and instance B's 3rd request in that batch correctly returned `429 rate_limited` — the combined
cross-process count, not either process's own local count, is what tripped the limiter. Confirmed via
`redis-cli keys`/`ttl` that the real `ratelimit:login-ip:127.0.0.1` key existed with a live TTL. Cleared the
test key afterward and confirmed a real demo-tenant login still succeeds normally. This is the load-bearing
proof for this milestone: the exact failure mode the in-memory limiter had (each of N horizontally-scaled
instances independently allowing up to the configured limit, for an effective `N × limit` combined) is now
provably closed.

## Milestone 23 — Architecture Decisions (made or refined during implementation)

- **Fixed-window (`INCR`+`EXPIRE`) over a Redis-sorted-set sliding window** — the simpler of the two standard
  Redis rate-limiting patterns, and the one the original Milestone 1 docstring specifically named. A true
  sliding window would need `ZADD`/`ZREMRANGEBYSCORE`/`ZCARD` and doesn't meaningfully improve security
  posture for this use case (login-attempt throttling, not billing-grade metering) enough to justify the
  extra complexity.
- **No fallback path if Redis is unreachable** — the app already requires Redis for Celery in every
  environment this runs in (local dev, CI, and the documented Docker Compose stack), so the rate limiter
  inherits an existing infrastructure dependency rather than adding a new hard requirement. If Redis is down,
  login requests fail outright rather than silently disabling rate limiting — judged the safer failure mode
  for a security control.
- **Kept the old class's exact `check(key, *, limit, window_seconds)` shape**, only changing it from sync to
  async — minimizes the diff at the three call sites and keeps the interface self-documenting rather than
  redesigning it while also changing its backing store.

## Milestone 23 — Known Limitations

- **Fixed-window boundary effect**: a client can send up to `limit` requests just before a window boundary
  and another `limit` just after, getting up to `2 × limit` through in a short span. Documented in the
  `RedisRateLimiter` docstring itself, not just here. A sorted-set sliding window would close this if it's
  ever judged worth the added complexity.
- **No per-tenant or per-role rate-limit override** — the three limits (`rate_limit_login_per_minute`,
  `rate_limit_login_per_hour_per_account`, and the hardcoded `5`/hour on forgot-password) are global
  `Settings` values, same as before this milestone. Not a regression, but also not improved here.
- **No frontend automated tests were added** — this milestone touched no frontend code.

## Milestone 23 — Unresolved Risks

- Carried over from Milestones 1-22 (no dependency/container/secret scanning in CI, Docker Compose still
  unverified end-to-end, the scoring formulas' simplicity, the inherent stakes of unattended action
  execution, the evidence permission-per-target design, the control-scoring weights, the
  cross-cutting-permission decisions, the widened-RLS-by-data-value pattern, the threat-intel
  confidence-to-severity thresholds, the HTTP-file domain-verification substitution, the terminal-`archived`
  tenant status, the hardcoded MFA admin-role set, MFA backup/recovery codes, the
  RLS-silently-no-ops-without-tenant-context hazard, no pager UI beyond a 100-row cap on the three
  grant-gated drill-downs) — none were touched this milestone and remain open.
- **The in-memory rate limiter, carried since Milestone 1, is now resolved** — removed from this list.
- **The fixed-window boundary effect** (new this milestone — see Known Limitations above) is a small,
  understood, deliberate tradeoff.
- **No obvious next breadcrumb is currently named**, same as after Milestone 22. CI dependency/secret
  scanning is the next most concretely-actionable candidate on the remaining list (it, too, has an
  identifiable, scoped shape: add `pip-audit`/`npm audit`/a container-scanning step to
  `.github/workflows/ci.yml`), but this is a real recommendation, not a claim that it's the only option.

## Milestone 23 — Pending Approvals

- This Milestone 23 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and the live cross-process proof is the strongest
  verification this session has done for a non-user-facing infrastructure change.
- If you'd like a default proposed again rather than an open question, CI dependency/secret scanning is the
  next-most-concrete remaining candidate (see Unresolved Risks above) and would be the default absent other
  direction.

## Milestone 23 — Next Action

Awaiting your review or direction for Milestone 24.

## Milestone 24: MFA Backup/Recovery Codes

**Scope chosen by explicit user instruction** — the user asked to run all tests, report what's
remaining, and complete the project. The remaining-work review categorized items as structurally
blocked (no Docker daemon in this environment), concretely closable, or intentional design tradeoffs,
and this is the first of five closable items being worked through in sequence: self-service MFA
recovery, carried as an Unresolved Risk since Milestone 13.

### Backend (`apps/api`)
- **New `MfaBackupCode` table** — same generate-hash-store-consume shape as every other token table in
  `modules.identity` (`PasswordResetToken`, `EmailVerificationToken`, `MfaChallengeToken`), but
  deliberately no `expires_at`: a backup code is meant to sit unused for months until the one day it's
  actually needed.
- **10 codes generated on `confirm_mfa_enrollment`**, format `XXXXX-XXXXX` drawn from an alphabet that
  excludes visually-ambiguous characters (0/O, 1/I/L) since these are meant to be handwritten or read off
  a screen during a real recovery. Only each code's SHA-256 hash is ever persisted; the plaintext batch is
  returned to the caller exactly once, in the `/mfa/confirm` response.
- **`consume_mfa_challenge_token` now accepts either a TOTP `code` or a `backup_code`** — exactly one,
  enforced in the service layer since "exactly one of two optional fields" isn't a simple pydantic field
  constraint. A backup code is single-use (marked `used_at` on success) and only usable at the login
  challenge — not for `disable_mfa` or `step_up`, which still require the authenticator device, the same
  trust level those already had.
- **New `POST /api/auth/mfa/backup-codes/regenerate`** — requires a fresh TOTP code (the same trust level
  `disable_mfa` already requires), invalidates every existing code, and issues a new batch of 10. A user
  who has lost both their authenticator and every backup code has no self-service path here — a
  deliberately narrower scope than a full account-recovery flow, documented as a Known Limitation rather
  than silently left ambiguous.
- **`disable_mfa` now also deletes all backup codes** for the account — they're moot once MFA itself is
  off.
- **A backup-code login is tagged in the audit trail** — `_complete_login` gained an `mfa_method` param
  (`"totp"` or `"backup_code"`), recorded in `auth.login`'s `context`, so a login that bypassed the normal
  second factor is distinguishable from a routine one without needing a separate audit action name.

### Frontend (`apps/web`)
- **Security settings page**: confirming MFA enrollment now shows a one-time "Save your backup codes"
  card with all 10 codes, dismissed explicitly by the user ("I've saved these codes") rather than
  auto-hiding. A "Regenerate backup codes" control (requiring a fresh TOTP code) reuses the same
  once-only display card.
- **Login page's MFA-challenge step**: a "Lost your device? Use a backup code" toggle switches the
  6-digit TOTP input for an 11-character backup-code input, calling the same `/mfa/verify-login` endpoint
  with `backup_code` instead of `code`.

## Milestone 24 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| Confirming MFA enrollment returns exactly 10 unique, correctly-formatted backup codes | ✅ | `test_confirm_mfa_returns_ten_unique_backup_codes`; live-verified — 10 real codes captured from the settings page UI |
| A backup code can complete the login challenge in place of a TOTP code | ✅ | `test_login_with_backup_code_when_totp_unavailable`; live-verified end-to-end via a real browser, landing on the real dashboard |
| A backup code is single-use | ✅ | `test_backup_code_is_single_use` — reusing the same code on a second login attempt returns 401 |
| A wrong/unknown backup code is rejected | ✅ | `test_wrong_backup_code_is_rejected` |
| Regenerating backup codes requires a valid TOTP code and invalidates the old batch | ✅ | `test_regenerate_backup_codes_invalidates_old_ones` — an old code returns 401 after regeneration, a new one succeeds |
| Disabling MFA clears all backup codes | ✅ | `test_disable_mfa_clears_backup_codes` — direct DB check confirms zero rows remain |
| No regressions to existing MFA/step-up flows | ✅ | Full `test_mfa.py` suite (14 tests, up from 6) and `test_security_policy_enforcement.py` pass unchanged |
| Backend tests pass | ✅ | **236/236** passing (`pytest -q` in `apps/api`, up from 230 — 8 new backup-code tests), `ruff check .` clean |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 31/31 routes |

## Milestone 24 — Test Results (as actually executed in this session)

```
apps/api: pytest -q                   → 236 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 31/31 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Next.js stack, driven by headless Chromium, against the
real demo tenant owner account (previously MFA-free): enabled MFA through the real settings-page flow,
computed the TOTP confirmation code via the Web Crypto API in-browser (RFC 6238, the same algorithm
`pyotp` uses server-side — nothing mocked), captured all 10 real backup codes as rendered in the UI,
logged out, triggered a real login challenge, clicked "Lost your device? Use a backup code," submitted one
of the captured codes, and confirmed the browser landed on the real dashboard — a genuine login completed
without ever entering a TOTP code. Disabled MFA afterward to restore the demo tenant to its normal
(MFA-free) state for future milestones' verification.

## Milestone 24 — Architecture Decisions (made or refined during implementation)

- **Backup codes are login-challenge-only, not a general MFA-proof substitute.** `disable_mfa` and
  `step_up` still require a TOTP code. Allowing a backup code to disable MFA entirely would mean a single
  leaked backup code could permanently strip an account's second factor; requiring the device itself for
  that specific action is a deliberately higher bar.
- **Regeneration requires TOTP, not just an authenticated session or a spare backup code.** This means a
  user who has exhausted every backup code and lost their device has no self-service recovery path — a
  real, documented gap (see Known Limitations) rather than a broader "logged-in users can always
  regenerate" design that would weaken what a backup code proves.
- **No expiry on backup codes**, unlike every other token table in `modules.identity`. A code is meant to
  sit dormant for months; adding a TTL would defeat the point of a recovery mechanism for a rarely-touched
  credential.

## Milestone 24 — Known Limitations

- **No path back if both the authenticator and every backup code are lost.** Regeneration requires a valid
  TOTP code; there is no admin-assisted or email-based account-recovery flow. A deliberately narrower scope
  than a full recovery system — flagged explicitly rather than implied to be complete.
- **No download/print/copy affordance on the backup-codes card** — a user must manually select and copy the
  10 codes shown. A reasonable UX polish item, not attempted here to keep this milestone's scope to the
  actual security gap (self-service recovery existing at all) rather than presentation niceties.
- **No frontend automated tests were added** for the new backup-code UI — same gap and rationale as every
  prior milestone's new UI: verified manually end-to-end via Playwright, passes lint/typecheck/build, but no
  dedicated Vitest coverage.

## Milestone 24 — Unresolved Risks

- Carried over from Milestones 1-23 (no dependency/container/secret scanning in CI, Docker Compose still
  unverified end-to-end, the scoring formulas' simplicity, the inherent stakes of unattended action
  execution, the evidence permission-per-target design, the control-scoring weights, the
  cross-cutting-permission decisions, the widened-RLS-by-data-value pattern, the threat-intel
  confidence-to-severity thresholds, the HTTP-file domain-verification substitution, the terminal-`archived`
  tenant status, the hardcoded MFA admin-role set, the RLS-silently-no-ops-without-tenant-context hazard, the
  fixed-window rate-limiter boundary effect, no pager UI beyond a 100-row cap on the three grant-gated
  drill-downs, object storage and real email delivery still simulated) — none were touched this milestone
  and remain open.
- **MFA backup/recovery codes, carried since Milestone 13, is now resolved** — removed from this list.
- **No path back if both the authenticator and every backup code are lost** (new this milestone — see Known
  Limitations above) is a small, understood, deliberately out-of-scope gap.

## Milestone 24 — Pending Approvals

- This Milestone 24 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and the live end-to-end proof (a real login completed
  via backup code alone) is the strongest verification available for this feature.
- Continuing directly to Milestone 25 (CI dependency/secret scanning) per the "complete the project"
  instruction, working through the remaining closable items in the order presented.

## Milestone 24 — Next Action

Milestone 25 in progress.

## Milestone 25: CI Dependency/Secret Scanning

**Scope chosen by explicit user instruction** — continuing directly from Milestone 24 as the second of
five closable items identified when the user asked to run all tests, report what's remaining, and
complete the project. This closes the oldest-standing item on the Unresolved Risks list besides the
in-memory rate limiter (already resolved in Milestone 23): no dependency or secret scanning in CI,
carried since Milestone 1.

### What this milestone actually did
Rather than just wiring scanning tools into CI and leaving them to report a pre-existing backlog of
findings, this milestone ran each tool for real against the live repository first, reviewed every
finding, fixed what was safely fixable, and only used an ignore/allowlist mechanism for findings that
require a larger, riskier change (a dependency's major-version bump) explicitly out of scope for "add
scanning."

**`pip-audit` (Python dependencies):** Found 22 known vulnerabilities across 5 packages on first run.
Upgraded `cryptography` (44.0.0 → 49.0.0), `python-multipart` (0.0.20 → 0.0.32), `pytest` (8.3.4 → 9.0.3),
`pytest-asyncio` (0.25.0 → 1.4.0 — required for pytest 9 compatibility), and added an explicit
`setuptools>=83.0.0` dev-dependency pin. Full 236-test backend suite re-run and passing after each bump.
This closed all vulnerabilities except 7 `starlette` CVEs, none of which have a fix version inside the
range FastAPI 0.115.6 itself constrains starlette to (`<0.42.0`) — fixing these requires a FastAPI
major-version bump (0.115 → 0.139, many minor releases), judged too large and risky a change to fold into
a CI-tooling milestone. These 7 IDs are explicitly listed with `--ignore-vuln` in the CI step, each
justified in a comment rather than silently suppressed.

**`pnpm audit` (JS dependencies):** Found 24 vulnerabilities (including 1 critical: a Next.js middleware
authorization bypass) on first run, entirely in the `next` package. Upgraded `next` and
`eslint-config-next` from 14.2.18 to 14.2.35 (the latest patch release still on the 14.x line) — this
alone resolved the critical and most of the high/moderate findings, since their fixes exist within 14.x.
The remaining 15 lower-severity findings require Next.js 15.x, a major-version bump out of scope here for
the same reason as FastAPI. `--ignore-unfixable` (a built-in pnpm flag, not a hand-maintained ID list)
correctly recognizes these as unresolvable within the current exact-pinned major version and excludes
them, while still failing on anything with a fix available in-place.

**Secret scanning (`detect-secrets`):** No tool was already present in this environment or installable via
the direct-download path the network policy allows (`github.com` release downloads are blocked by the
outbound proxy; `pypi.org` is allowlisted), so `detect-secrets` — a well-known, pip-installable scanner —
was used instead of `gitleaks`. Ran a full scan against the tracked repository (excluding `.venv`,
`node_modules`, `.next`, `pnpm-lock.yaml`) and manually reviewed every one of the 47 findings across 47
files: all were confirmed false positives — dev-only fictional credentials already labelled as such
(`gridkeep`/`gridkeep` Postgres passwords in `docker-compose.yml`/`ci.yml`, the demo tenant's documented
fictional password), Alembic migration revision hashes (which are just high-entropy-looking autogenerated
IDs), and one code constant (`_BACKUP_CODE_ALPHABET` from Milestone 24) that happens to look like a
high-entropy string to the heuristic. Committed a `.secrets.baseline` recording these as reviewed, so CI
only fails on genuinely new secrets — verified live by planting a fake AWS key in a scratch file and
confirming `detect-secrets-hook` correctly flagged and failed on it (exit 1), then confirming a scan of the
real repository against the baseline passes clean (exit 0).

### CI (`.github/workflows/ci.yml`)
- **Backend job**: new "Dependency vulnerability scan (pip-audit)" step after the ruff step, with the 7
  starlette `--ignore-vuln` IDs and an inline comment explaining why each is excluded.
- **Frontend job**: new "Dependency vulnerability scan (pnpm audit)" step after install, using
  `--ignore-unfixable` with an inline comment.
- **New `secret-scan` job**: installs `detect-secrets` and runs `detect-secrets-hook --baseline
  .secrets.baseline` against every tracked file (excluding vendored/generated directories).

## Milestone 25 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| pip-audit runs clean against the actual dependency set, with only explicitly-justified exclusions | ✅ | Live-verified: `pip-audit -l --ignore-vuln ...` (the exact CI command) exits 0 with "No known vulnerabilities found, 9 ignored" |
| pnpm audit runs clean against the actual dependency set, with only explicitly-justified exclusions | ✅ | Live-verified: `pnpm audit --ignore-unfixable` (the exact CI command) exits 0 |
| Secret scanning is real, not a rubber stamp — every finding was actually reviewed | ✅ | All 47 findings across 47 files individually reviewed and spot-checked in this session; none were real secrets |
| The secret-scanning gate has real teeth (would catch a genuinely new secret) | ✅ | Live-verified: a fake AWS key planted in a scratch file was correctly flagged and failed the exact CI command (exit 1); the real repository content passes (exit 0) |
| The dependency upgrades performed don't regress existing functionality | ✅ | Full 236-test backend suite passes after each bump; full frontend lint/typecheck/vitest/build suite passes on Next.js 14.2.35; live E2E MFA enroll/backup-code-login/disable round-trip (which exercises `cryptography`'s AES-GCM encryption on a real secret) still works end-to-end |
| Backend tests pass | ✅ | **236/236** passing (`pytest -q` in `apps/api`, count unchanged — this milestone added no new tests, since the fix is dependency versions, not application behavior), `ruff check .` clean |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 31/31 routes (on Next.js 14.2.35) |

## Milestone 25 — Test Results (as actually executed in this session)

```
apps/api: pytest -q                                    → 236 passed
apps/api: ruff check .                                 → All checks passed
apps/api: pip-audit -l --ignore-vuln ... (×7)           → No known vulnerabilities found, 9 ignored
apps/web: pnpm exec eslint .                            → 0 errors
apps/web: pnpm exec tsc --noEmit                        → 0 errors
apps/web: pnpm exec vitest run                          → 10 passed (3 files)
apps/web: next build                                    → succeeded, 31/31 routes
apps/web: pnpm audit --ignore-unfixable                 → No new vulnerabilities were ignored (clean)
repo root: detect-secrets-hook --baseline ... (tracked files) → clean; verified it fails on a planted fake secret
```

All of the above were executed directly in this session, using the exact commands now committed to
`.github/workflows/ci.yml` — not a close approximation. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Next.js stack on the upgraded dependencies: a full MFA
enroll → confirm (real backup codes shown) → logout → login-challenge → backup-code login → disable cycle
via a real headless browser, the same test used to verify Milestone 24, re-run here specifically because it
exercises `cryptography`'s encryption path (which changed from 44.0.0 to 49.0.0) on a real secret rather
than relying on the automated test suite alone to catch a subtle behavioral change in a security-critical
library.

## Milestone 25 — Architecture Decisions (made or refined during implementation)

- **Fixed what was safely fixable; documented and ignored what wasn't, rather than either silently
  suppressing everything or leaving the newly-added CI gate red on day one.** A vulnerability scanner that
  immediately fails the build it was just added to (on pre-existing, not-currently-actionable findings)
  tends to get disabled rather than fixed — explicit, justified `--ignore-vuln`/`--ignore-unfixable` usage
  keeps the gate meaningful for genuinely new issues going forward.
- **`detect-secrets` over `gitleaks`**, a build-environment constraint, not a technical preference —
  `gitleaks`' binary releases are hosted on `github.com`, which this session's outbound network policy
  blocks for direct downloads (only `pypi.org`, `npmjs.org`, and a few others are allowlisted). This is
  disclosed explicitly rather than silently substituted without explanation.
- **A committed `.secrets.baseline`, not a bare `detect-secrets scan` with no baseline.** Without a
  baseline, every future CI run would re-flag the same 47 already-reviewed false positives, which is
  exactly the kind of noisy gate that gets ignored or disabled. The baseline makes the scan only ever
  surface genuinely new findings.
- **Upgraded `next`/`eslint-config-next` and `cryptography`/`python-multipart`/`pytest`/`pytest-asyncio`
  together with the scanning work, not as separate follow-up milestones** — since the whole point of
  adding a scanner is to act on what it finds, leaving newly-discovered, safely-fixable vulnerabilities
  unfixed in the same milestone that found them would be a strange split.

## Milestone 25 — Known Limitations

- **`starlette` remains on 0.41.3 with 7 known CVEs**, blocked by FastAPI 0.115.6's own version pin
  (`<0.42.0`). Fixing this requires upgrading FastAPI across many minor versions (0.115 → 0.139), which
  touches request/response handling, dependency injection, and middleware behavior broadly enough to
  deserve its own dedicated milestone with focused regression testing, not a rushed bump here.
- **`next` remains on 14.2.35 with several lower-severity (no critical/high remaining) CVEs**, whose fixes
  require the 15.x line — a major-version bump with its own App Router / React Server Component migration
  considerations, same reasoning as the FastAPI deferral.
- **The secret-scanning baseline requires manual maintenance** — a legitimate new secret accidentally
  committed alongside a baseline update (rather than caught fresh) could theoretically slip through if
  someone regenerates the baseline carelessly instead of reviewing new findings individually. Standard,
  accepted operational risk for this class of tool, not unique to this implementation.
- **No frontend or backend automated tests were added** — this milestone is CI configuration and dependency
  versions, not new application behavior.

## Milestone 25 — Unresolved Risks

- Carried over from Milestones 1-24 (Docker Compose still unverified end-to-end, the scoring formulas'
  simplicity, the inherent stakes of unattended action execution, the evidence permission-per-target
  design, the control-scoring weights, the cross-cutting-permission decisions, the
  widened-RLS-by-data-value pattern, the threat-intel confidence-to-severity thresholds, the HTTP-file
  domain-verification substitution, the terminal-`archived` tenant status, the hardcoded MFA admin-role
  set, the RLS-silently-no-ops-without-tenant-context hazard, the fixed-window rate-limiter boundary
  effect, no pager UI beyond a 100-row cap on the three grant-gated drill-downs, object storage and real
  email delivery still simulated, no path back if both the authenticator and every backup code are lost) —
  none were touched this milestone and remain open.
- **No dependency/container/secret scanning in CI, carried since Milestone 1, is now resolved** — removed
  from this list.
- **`starlette`'s 7 CVEs, blocked by FastAPI's own pin** (new this milestone — see Known Limitations
  above), and **`next`'s remaining lower-severity CVEs, blocked by the 15.x requirement** (also new this
  milestone) are both explicit, documented, ignored-with-justification risks, not silent gaps.
- **Container image scanning was not added** — this project has no committed Dockerfile build step in CI
  (the `docker-compose.yml` stack itself remains unverified end-to-end, per the carried-over risk above),
  so there is no built image to scan yet. Dependency and secret scanning were completed; container scanning
  would need Docker Compose verification to precede it.

## Milestone 25 — Pending Approvals

- This Milestone 25 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, both scanning gates are live-verified to have real
  teeth (not just present-but-toothless), and every accepted-risk exclusion is individually justified in
  both the CI file and this document rather than bulk-suppressed.
- Continuing directly to Milestone 26 (pager UI on the grant-gated drill-downs) per the "complete the
  project" instruction.

## Milestone 25 — Next Action

Milestone 26 in progress.

## Milestone 26: Pager UI on the Grant-Gated Drill-Downs

**Scope chosen by explicit user instruction** — the third of five closable items identified from the
user's "run all tests, report what's remaining, complete the project" request. Closes the "no pager UI
beyond a 100-row cap" gap flagged in Milestone 21, replacing the fixed `limit=100` cap on the tenant
workspace snapshot page's three grant-gated drill-downs with real Previous/Next pagination, using the
`limit`/`offset` support Milestone 21 already built server-side.

### Frontend (`apps/web`) — the only surface this milestone touched
- **`PAGE_SIZE = 5`** replaces the fixed `limit=100` on all three drill-down queries (findings, incidents,
  integrations) on `app/platform/tenants/[tenantId]/workspace/page.tsx`. Each section gets its own `page`
  state (`findingsPage`, `incidentsPage`, `integrationsPage`), included in its query key so React Query
  caches each page distinctly rather than treating pagination as a single evolving query.
- **A small reusable `Pager` component** (Previous/Next buttons + "Page N" label) added once and used by
  all three sections rather than duplicating the same markup three times.
- **"Has a next page" is inferred from a full page being returned** (`data.length === PAGE_SIZE`) — there's
  no total-count endpoint, so this is the standard limit/offset heuristic. The known edge case (a result
  set landing exactly on a page boundary shows one extra enabled-but-empty "Next" click) is documented
  below rather than silently accepted as invisible.
- **Card headers dropped their inline counts** (`All findings (${count})` → `All findings`) since the
  count now reflects only the current page's size, not the tenant's true total — showing it would have
  been actively misleading rather than merely incomplete.

## Milestone 26 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| Findings/incidents/integrations drill-downs paginate in fixed-size pages instead of a flat 100-row cap | ✅ | Live-verified against the demo tenant's 7 real findings: page 1 shows exactly 5, page 2 shows the remaining 2, with zero overlap between the two sets |
| "Next" is disabled once a page is not full | ✅ | Live-verified: `Next` enabled on findings page 1 (5 items = `PAGE_SIZE`), disabled on page 2 (2 items < `PAGE_SIZE`) |
| "Previous" returns to the exact same page-1 content | ✅ | Live-verified: clicking `Previous` from page 2 reproduced page 1's row titles exactly |
| Real `limit`/`offset` query params are sent, not just a UI-only slice of a larger fetch | ✅ | Live-verified via captured network responses: `.../findings?limit=5&offset=0` then `.../findings?limit=5&offset=5` |
| No regressions to the surrounding page (member list, snapshot tiles, grant-gating) | ✅ | Live screenshot shows all sections rendering correctly together with real demo-tenant data |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 31/31 routes |
| Backend unaffected | ✅ | No backend files changed this milestone — stated explicitly rather than re-running the unaffected 236-test suite for a frontend-only change |

## Milestone 26 — Test Results (as actually executed in this session)

```
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 31/31 routes
```

No backend code was touched this milestone (`limit`/`offset` support already existed from Milestone 21),
so the backend test suite was not re-run — noted explicitly rather than silently reused from a prior
milestone's log. Manual, real end-to-end verification performed against a live
Postgres/Redis/`uvicorn`/Next.js stack: requested and approved a real support access grant, opened the
tenant workspace page for the demo tenant (7 real findings, 5 real integrations, 0 incidents), confirmed
page 1 of findings showed exactly 5 real rows with `Next` enabled, clicked `Next` and confirmed the
remaining 2 rows appeared with zero overlap and `Next` now disabled, clicked `Previous` and confirmed page
1's exact content reappeared, and confirmed via captured network responses that the browser actually sent
`limit=5&offset=0` then `limit=5&offset=5` to the real API — not a client-side slice of a larger
already-fetched list. Revoked the test grant afterward.

## Milestone 26 — Architecture Decisions (made or refined during implementation)

- **`PAGE_SIZE = 5`, not a larger production-typical page size**, chosen specifically because it's small
  enough to actually exercise multi-page behavior against the current demo tenant's real data (7 findings)
  in live verification, while still being a reasonable size for a real support-drill-down view (which is
  inherently a narrow, occasional-use surface, not a high-volume list). If tenant data volumes grow
  significantly, this is a one-constant change, not a redesign.
- **No total-count / page-number display beyond "Page N"** — building a jump-to-page or total-pages
  indicator would require either a `COUNT(*)` query added to each of the three drill-down endpoints or an
  approximate/cached count, judged unnecessary complexity for what's fundamentally a "scroll forward through
  a list" support tool, not a reporting UI.
- **Per-section page state, not a single shared page number** — findings, incidents, and integrations are
  independent lists with independent lengths; forcing them to share one page cursor would either be
  meaningless or would require them to always fetch in lockstep for no benefit.

## Milestone 26 — Known Limitations

- **The "has next page" heuristic has a known edge case**: a result count that's an exact multiple of
  `PAGE_SIZE` shows `Next` enabled on the last real page, and clicking it lands on a legitimately empty
  page (the UI does render "No more findings." — not broken, just a possible one-click surprise). Fixing
  this properly requires a total-count endpoint, judged out of scope for this pass — see Architecture
  Decisions above.
- **No frontend automated tests were added** for the pagination UI — same gap and rationale as every prior
  milestone's new UI: verified manually end-to-end via Playwright, passes lint/typecheck/build, but no
  dedicated Vitest coverage.

## Milestone 26 — Unresolved Risks

- Carried over from Milestones 1-25 (Docker Compose still unverified end-to-end, the scoring formulas'
  simplicity, the inherent stakes of unattended action execution, the evidence permission-per-target
  design, the control-scoring weights, the cross-cutting-permission decisions, the
  widened-RLS-by-data-value pattern, the threat-intel confidence-to-severity thresholds, the HTTP-file
  domain-verification substitution, the terminal-`archived` tenant status, the hardcoded MFA admin-role
  set, the RLS-silently-no-ops-without-tenant-context hazard, the fixed-window rate-limiter boundary
  effect, object storage and real email delivery still simulated, no path back if both the authenticator
  and every backup code are lost, `starlette`'s CVEs blocked by FastAPI's pin, `next`'s remaining CVEs
  requiring the 15.x line) — none were touched this milestone and remain open.
- **No pager UI beyond a 100-row cap on the three grant-gated drill-downs, carried since Milestone 21, is
  now resolved** — removed from this list.
- **The exact-page-boundary "Next" edge case** (new this milestone — see Known Limitations above) is a
  small, understood, deliberate tradeoff pending a future total-count endpoint if ever prioritized.

## Milestone 26 — Pending Approvals

- This Milestone 26 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, and the live network-level proof (real `limit`/`offset` params,
  not a client-side slice) is the strongest verification available for confirming this is real pagination
  and not a cosmetic-only change.
- Continuing directly to Milestone 27 (DNS TXT domain verification) per the "complete the project"
  instruction.

## Milestone 26 — Next Action

Milestone 27 in progress.

## Milestone 27: DNS TXT Domain Verification

**Scope chosen by explicit user instruction** — the fourth of five closable items from the user's "run all
tests, report what's remaining, complete the project" request. Adds DNS TXT as a second domain-ownership
verification method alongside Milestone 11's HTTP file, closing that milestone's own documented gap.

### A real constraint, checked directly before writing any code
Milestone 11's own code comments already explained why DNS TXT wasn't the first method built: "raw DNS
queries are network-blocked in the environment this was built in." Before assuming that no longer applied,
this milestone re-tested it directly — a `dnspython` query to the system-configured resolver (`8.8.8.8`,
matching `/etc/resolv.conf`) for a real domain's TXT record timed out after 5+ seconds. **That constraint is
still real and still true.** Rather than treat this as a hard blocker (the same way Docker Compose
verification and a live GitHub Actions run were already categorized as out of reach in this environment),
this milestone found a middle path: a **real local DNS server on loopback** answers a **real UDP DNS
protocol exchange** in this environment (confirmed directly — a hand-rolled server on `127.0.0.1` answered
a real `dnspython` TXT query correctly). This is exactly the same pattern Milestone 11's own HTTP-file tests
already use — a real local HTTP server standing in for a live one, not a mocked network call — just applied
to DNS instead of HTTP. It is real DNS, real code, real network I/O; only the live public internet path is
unavailable here, and that's disclosed explicitly below rather than glossed over.

### Backend (`apps/api`)
- **New `dnspython==2.8.0` direct dependency** — was already present transitively (via `email-validator`),
  now declared explicitly since application code uses it directly.
- **`_verify_via_dns_txt`** queries `_gridkeep-verification.{domain}` (a dedicated subdomain, not the
  domain's apex — the same pattern real DNS verification schemes like Google Search Console use, so this
  never collides with a domain's existing TXT records such as SPF or DKIM) via `dns.asyncresolver`, checking
  whether any returned TXT record contains the domain's verification token.
- **`verify_domain` now dispatches on a `method` parameter** (`"http_file"` or `"dns_txt"`, defaulting to
  `"http_file"` for full backward compatibility with existing tenant-facing behavior and tests), refactored
  from a single HTTP-only function into a dispatcher plus two private per-method implementations
  (`_verify_via_http_file`, `_verify_via_dns_txt`).
- **`DomainRead` gained a `dns_txt_record_name` field** alongside the existing `verification_file_url`, so
  the frontend can show correct instructions for either method without separate lookups.
- **The verification-method choice is now tagged on the audit record** (`context={"domain": ..., "method":
  ...}`), extending the `context`-tagging convention established in Milestones 18-20 to this module.
- **`modules.tenancy.models.TenantDomain`'s docstring corrected in place** — it previously named DNS TXT as
  a "reasonable future method"; that's no longer accurate, so the docstring itself (living documentation,
  not a dated historical record like this file) was rewritten to describe both methods as they exist today.

### Frontend (`apps/web`)
- **A method radio selector** (HTTP file / DNS TXT record) on each unverified domain in the Attack Surface
  page, switching the displayed instructions (well-known URL vs. DNS record name) and passing the chosen
  `method` as a query parameter on verify.

## Milestone 27 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| DNS TXT verification succeeds when the correct token is present | ✅ | `test_verify_domain_dns_txt_succeeds_when_token_is_present`, against a real local DNS server (real UDP DNS protocol, not mocked) |
| DNS TXT verification fails when the token is wrong | ✅ | `test_verify_domain_dns_txt_fails_when_token_is_wrong` |
| DNS TXT verification fails cleanly when no record exists (NXDOMAIN) | ✅ | `test_verify_domain_dns_txt_fails_when_no_record_exists` |
| An unknown verification method is rejected | ✅ | `test_verify_domain_unknown_method_is_rejected` |
| Existing HTTP-file behavior is completely unchanged (default method, same tests) | ✅ | All 5 pre-existing HTTP-file tests pass unmodified |
| The frontend correctly switches instructions and sends the right method | ✅ | Live-verified: selecting "DNS TXT record" on a real added domain showed the correct `_gridkeep-verification.<domain>` record name; clicking "Verify now" sent a real DNS query and returned a real "No TXT record found" failure (not a fake success) |
| Backend tests pass | ✅ | **240/240** passing (`pytest -q` in `apps/api`, up from 236 — 4 new DNS TXT tests), `ruff check .` clean |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 31/31 routes |

## Milestone 27 — Test Results (as actually executed in this session)

```
apps/api: pytest -q                   → 240 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 31/31 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Next.js stack: added a real domain via the real demo
tenant owner account, confirmed the HTTP-file instructions render by default, selected "DNS TXT record" and
confirmed the instructions correctly switched to show `_gridkeep-verification.<domain>` with the same
token, clicked "Verify now," and confirmed the browser received a real "No TXT record found at
_gridkeep-verification.<domain>." message — the real code path genuinely attempted a real DNS query against
the tenant's real configured resolver and correctly did not produce a false-positive verification. Domain
removed afterward.

**What this live E2E does *not* claim**: a full DNS TXT *success* path against a real, publicly-resolvable
domain was not exercised live, since no such domain with DNS control was available in this session. That
success path is verified by the automated test suite against a real local DNS server instead (see above) —
stated explicitly rather than implied to have been proven the same way the HTTP-file method's live success
path was.

## Milestone 27 — Architecture Decisions (made or refined during implementation)

- **Re-verified a documented environmental constraint directly rather than assuming it still held (or
  assuming it didn't).** Milestone 11's docstring claim about DNS being network-blocked was six milestones
  and presumably a different underlying environment instance old; treating it as permanently true without
  re-checking would have been exactly the kind of stale-claim risk Milestone 22's audit was built to catch.
  Re-checking cost one command and confirmed the constraint is still accurate today.
- **A real local DNS server for tests, not a mocked resolver call.** Mocking `dns.asyncresolver.resolve`
  directly would have been faster to write but would only prove the response-parsing logic works, not that
  a real DNS query round-trip functions — the same standard the HTTP-file tests already hold themselves to,
  and the same reasoning connector code in this project always uses real (if simulated) I/O rather than
  fully-mocked calls.
- **`_gridkeep-verification.{domain}` subdomain, not a TXT record on the domain apex** — deliberately avoids
  ever colliding with a tenant's real SPF/DKIM/other TXT records, a correctness concern a naive
  apex-TXT-record design would have.
- **Default method stays `http_file`** — zero behavior change for any existing tenant, test, or integration
  that doesn't explicitly opt into DNS TXT.

## Milestone 27 — Known Limitations

- **DNS TXT's live *success* path was not exercised against the real public internet** — see the explicit
  callout in Test Results above. A tenant using this method in a real deployment (where DNS isn't blocked)
  would get a genuine result; this session simply couldn't observe a live success case itself.
- **No frontend automated tests were added** for the method selector — same gap and rationale as every
  prior milestone's new UI.

## Milestone 27 — Unresolved Risks

- Carried over from Milestones 1-26 (Docker Compose still unverified end-to-end, the scoring formulas'
  simplicity, the inherent stakes of unattended action execution, the evidence permission-per-target
  design, the control-scoring weights, the cross-cutting-permission decisions, the
  widened-RLS-by-data-value pattern, the threat-intel confidence-to-severity thresholds, the terminal-
  `archived` tenant status, the hardcoded MFA admin-role set, the RLS-silently-no-ops-without-tenant-context
  hazard, the fixed-window rate-limiter boundary effect, object storage and real email delivery still
  simulated, no path back if both the authenticator and every backup code are lost, `starlette`'s CVEs
  blocked by FastAPI's pin, `next`'s remaining CVEs requiring the 15.x line, the exact-page-boundary "Next"
  pagination edge case) — none were touched this milestone and remain open.
- **The HTTP-file-only domain-verification substitution, carried since Milestone 11, is now resolved** —
  removed from this list.
- **DNS TXT's live success path being unverified against the real internet** (new this milestone — see
  Known Limitations above) is an environment constraint, not a code gap — the automated test suite exercises
  the real protocol against a real local server instead.

## Milestone 27 — Pending Approvals

- This Milestone 27 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass against a real local DNS server, and the one honest
  limitation (no live public-internet success case observed) is stated explicitly rather than implied away.
- Continuing directly to Milestone 28 (real evidence storage + real email dispatch), the last of the five
  closable items, per the "complete the project" instruction.

## Milestone 28: Real Evidence File Storage + Real Email Dispatch

**Scope chosen by explicit user instruction** — the fifth and last of five closable items from the user's
"run all tests, report what's remaining, complete the project" request. Closes two long-standing dormant
settings blocks in `core/config.py` (`mail_capture_*`, `object_storage_*`) that had sat unused since
Milestone 1, and the `email_dispatch_simulated` log-line stand-in used by onboarding, invitations, and
password reset since Milestone 1.

### Real email dispatch (`core/email.py`)
- **`send_email()`** is a genuine `smtplib` client (stdlib), not a log line — builds a real RFC 5322
  message via `email.message.EmailMessage` and sends it over a real SMTP connection to
  `settings.mail_capture_host`/`mail_capture_port` (already-defined settings, pointed at Mailhog's default
  port since Milestone 1, never previously used). Raises on failure rather than swallowing it.
- All three `email_dispatch_simulated` call sites now call `send_email()` with a real subject/body:
  `modules/tenancy/service.py` (email verification on onboarding), `modules/permissions/routes.py`
  (invitations), `modules/identity/routes.py` (password reset).
- **New `aiosmtpd==1.4.6` dev dependency** — a real, pure-Python SMTP *server* used only in tests, to
  genuinely exercise the SMTP client rather than mock it. This is the third use of the project's
  "real local protocol server" pattern (`_local_well_known_server` for HTTP in Milestone 11,
  `_local_dns_txt_server` for DNS in Milestone 27, and now a session-scoped `aiosmtpd` `Controller` in
  `conftest.py` for SMTP) — bound to the same host/port production points at Mailhog, so every existing
  test that triggers an email (onboarding, invitations, password reset) now exercises a real SMTP
  round-trip, not a mock. Captured messages are exposed to tests via a `sent_emails` fixture.

### Real evidence file storage (`core/storage.py`, `modules/compliance`)
- **`core/storage.py`** writes/reads/deletes real files on local disk under `settings.evidence_storage_root`
  (new setting, default `var/evidence-storage`), scoped per-tenant (`{root}/{tenant_id}/{evidence_id}__
  {sanitized_filename}`), with filename sanitization and a path-traversal guard (`Path.is_relative_to`)
  on read/delete.
- **Deliberately not the dormant `object_storage_*` (S3/MinIO-compatible) settings** — a real MinIO instance
  needs a Docker daemon this sandboxed environment doesn't have (same constraint that's kept Docker Compose
  itself unverified end-to-end since Milestone 1). This is the same tradeoff Milestone 27 made for DNS TXT
  verification: a genuinely real, but intentionally scoped-down, local substitute for the unreachable
  production-shaped dependency — disclosed explicitly here rather than glossed over. `object_storage_*`
  remains dormant.
- **`EvidenceRecord` gained four nullable columns** (`file_path`, `file_name`, `file_content_type`,
  `file_size_bytes`), populated only for `evidence_type == "document"` rows — migration
  `636ee68487fe_milestone28_evidence_file_columns`.
- **`CreateEvidenceRequest`'s `evidence_type` pattern narrowed to `url|note`** — `document` evidence now
  requires real file bytes, which don't fit a JSON body, so it's created through a dedicated route instead.
- **New `POST /api/evidence/document`** (multipart form: `title`, `description`, `target_type`, `target_id`,
  `collected_at`, `file`) — same permission-per-target-type gate as the existing JSON create route
  (`compliance.manage`/`incidents.manage`), a 10 MiB size cap, and rejects empty files.
- **New `GET /api/evidence/{evidence_id}/file`** — downloads the real stored bytes with the original
  filename and content type (`Content-Disposition: attachment`), gated on `evidence.view` and tenant-scoped
  (cross-tenant access returns 404, same as the rest of the evidence API).
- **`delete_evidence` now also deletes the underlying file** from disk when one exists.

### Frontend (`apps/web`)
- **`apiClient.postForm()`** — new multipart-form request helper (no `Content-Type` header, letting the
  browser set the boundary) alongside the existing JSON `post`/`patch`/`delete`.
- **`components/EvidenceList.tsx`** (shared by both the Compliance and Incident evidence panels): selecting
  "Document (file upload)" now shows a real file input instead of the old "reference only" label with no
  actual attachment path; uploads via `postForm` to the new multipart route; documents in the list render a
  real download link (file name + human-readable size) pointing at the new file route.

## Milestone 28 — Acceptance Criteria

| Criterion | Status | Evidence |
|---|:-:|---|
| Onboarding/invitation/password-reset emails are dispatched via a real SMTP client, not a log line | ✅ | `core/email.py`; all 3 call sites refactored |
| Real SMTP dispatch is exercised against a real local SMTP server in tests, not mocked | ✅ | `_smtp_capture` session fixture (`aiosmtpd` `Controller`) in `conftest.py`; `test_email.py`, plus assertions added to `test_auth_flow.py` and `test_rbac.py` |
| SMTP failures are not silently swallowed | ✅ | `test_send_email_raises_when_smtp_server_unreachable` |
| A document evidence upload writes a real file to local disk | ✅ | `test_document_evidence_upload_and_download_round_trips_real_bytes` |
| Downloaded bytes exactly match uploaded bytes | ✅ | Same test (assert equality) + live E2E (byte-for-byte file comparison) |
| Oversized uploads are rejected | ✅ | `test_document_evidence_rejects_oversized_file` (>10 MiB → 422) |
| Deleting evidence deletes the underlying file | ✅ | `test_deleting_document_evidence_removes_it_and_the_file` |
| Evidence files are tenant-isolated | ✅ | `test_document_evidence_file_scoped_to_own_tenant` (cross-tenant download → 404) |
| Frontend supports real file upload and download | ✅ | Live-verified via Playwright against the demo tenant: uploaded a real file through the browser, downloaded it, confirmed byte-for-byte match |
| Backend tests pass | ✅ | **248/248** passing (up from 240 — 8 new tests), `ruff check .` clean |
| Frontend lint/typecheck/tests/build pass | ✅ | eslint 0 errors, `tsc --noEmit` 0 errors, vitest 10/10 passing, `next build` 31/31 routes |

## Milestone 28 — Test Results (as actually executed in this session)

```
apps/api: pytest -q                   → 248 passed
apps/api: ruff check .                → All checks passed
apps/web: pnpm exec eslint .          → 0 errors
apps/web: pnpm exec tsc --noEmit      → 0 errors
apps/web: pnpm exec vitest run        → 10 passed (3 files)
apps/web: next build                  → succeeded, 31/31 routes
```

All of the above were executed directly in this session. Manual, real end-to-end verification also
performed against a live Postgres/Redis/`uvicorn`/Next.js stack, plus a standalone `aiosmtpd` capture
server started for this verification only (mirroring the test suite's fixture, pointed at the same
`mail_capture_host`/`mail_capture_port` the dev config already used):

- **Email**: submitted the real onboarding form as a new tenant in the browser; the standalone SMTP capture
  server received and printed a real message — correct `To`, `Subject: Verify your GRIDKEEP account`, and a
  real verification token in the body — proving the full path (form → API → `smtplib` → real SMTP wire
  protocol → server) genuinely works, not just the unit-tested slice of it.
- **Evidence file upload/download**: logged in as the demo tenant owner, opened a compliance control's
  evidence panel, selected "Document (file upload)," uploaded a real text file through the browser's file
  picker, confirmed the file name and size appeared in the evidence list, clicked the download link, and
  confirmed the downloaded file's bytes were identical to the originally uploaded file — genuine disk I/O
  round-tripped through the full stack, not a stub.

**What this live E2E does *not* claim**: it did not exercise a real S3/MinIO-compatible object store (the
dormant `object_storage_*` settings still point at an unreachable MinIO instance — no Docker daemon here),
and it did not exercise delivery to a real external mail relay or inbox (only the local capture server, same
scoping as production Mailhog in dev). Both are stated explicitly rather than implied to have been proven.

## Milestone 28 — Architecture Decisions (made or refined during implementation)

- **A real local SMTP server for the whole test session, not a per-test mock.** Extending the "real local
  protocol server" pattern (HTTP in M11, DNS in M27) to SMTP meant every *existing* test exercising
  onboarding/invitations/password-reset now genuinely proves the email path works, instead of adding
  isolated new tests alongside an unchanged mocked/logged path elsewhere.
- **Local-disk evidence storage instead of wiring up the dormant S3/MinIO settings.** A real MinIO instance
  needs Docker, which this environment doesn't have — the same reasoning that's kept Docker Compose itself
  unverified since Milestone 1. Building a genuinely real (if scoped-down) local-disk store was judged more
  valuable than either leaving evidence uploads entirely unbuilt or building an S3 client against a target
  that could never be exercised here.
- **Per-tenant subdirectories plus a path-traversal guard on every stored path.** Filenames are sanitized
  to their basename before being written; on read/delete, the resolved path is checked with
  `Path.is_relative_to` against the storage root before any file operation.
- **`document` evidence moved off the JSON create route entirely** rather than accepting file references or
  base64-encoding bytes into JSON — multipart form data is the correct shape for real file uploads, and
  splitting the route keeps the common note/url path unchanged for every existing caller.
- **10 MiB upload cap** — an explicit, if arbitrary, safety bound rather than no bound at all; not wired to
  a setting since nothing in this milestone's scope needed it configurable.

## Milestone 28 — Known Limitations

- **Real S3/MinIO object storage remains dormant** — `object_storage_*` settings are still unused; evidence
  files live on local disk instead. A production deployment with a real MinIO/S3 endpoint would need that
  wiring built separately.
- **Live delivery to a real external mail relay/inbox was not exercised** — only a local SMTP capture
  server, matching how Mailhog is used in the documented dev/Docker-Compose setup.
- **No virus/malware scanning on uploaded evidence files** — same standard as any other dev-stage file
  upload in this codebase; would need addressing before handling real untrusted uploads in production.
- **The 10 MiB size cap is a hardcoded constant**, not a configurable setting or per-tenant limit.
- **No frontend automated tests were added** for the new file upload/download UI — same recurring gap and
  rationale as every prior milestone's new UI.

## Milestone 28 — Unresolved Risks

- Carried over from Milestones 1-27 (Docker Compose still unverified end-to-end, the scoring formulas'
  simplicity, the inherent stakes of unattended action execution, the evidence permission-per-target
  design, the control-scoring weights, the cross-cutting-permission decisions, the
  widened-RLS-by-data-value pattern, the threat-intel confidence-to-severity thresholds, the terminal-
  `archived` tenant status, the hardcoded MFA admin-role set, the RLS-silently-no-ops-without-tenant-context
  hazard, the fixed-window rate-limiter boundary effect, no path back if both the authenticator and every
  backup code are lost, `starlette`'s CVEs blocked by FastAPI's pin, `next`'s remaining CVEs requiring the
  15.x line, the exact-page-boundary "Next" pagination edge case, DNS TXT's live success path being
  unverified against the real internet) — none were touched this milestone and remain open.
- **"Object storage and real email delivery still simulated," carried since Milestone 1, is now resolved
  for email** (genuinely real SMTP dispatch) **and partially resolved for evidence storage** (genuinely
  real local-disk file storage, though not the S3/MinIO-compatible object store the dormant settings
  describe) — removed from this list, replaced by the more precise limitations stated above.

## Milestone 28 — Pending Approvals

- This Milestone 28 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and every honest limitation (dormant S3/MinIO,
  no live external mail relay, no malware scanning, no frontend tests for the new UI) is stated explicitly.
- This closes the fifth and last of the five closable items identified from the "complete the project"
  instruction. The remaining open items are either structurally blocked in this sandboxed environment
  (Docker Compose end-to-end, a live GitHub Actions run) or intentional, previously-disclosed design
  tradeoffs (see Unresolved Risks above, carried across many milestones) — not gaps left to close.

## Post-Milestone 28: First Real Docker Compose Build Surfaced Three Latent Bugs

Every milestone since Milestone 1 has carried the same disclosed limitation: `docker compose up` was
config-validated (`docker compose config`) but never actually run end-to-end, because this build's sandbox
has no Docker daemon. That finally happened — the user ran it for real — and it failed on `web`'s build
stage. This is exactly the outcome that disclosure existed to warn about.

**Root cause, `infrastructure/docker/web.Dockerfile`** — three bugs in the `deps` stage, present unchanged
since the file was first written in Milestone 1:

1. `pnpm-lock.yaml` was never copied into the `deps` stage before `pnpm install --frozen-lockfile` ran.
   With no lockfile present, pnpm installed a permissive, unpinned dependency tree. The later `build`
   stage's `COPY . .` then brings in the *real* `pnpm-lock.yaml`, and pnpm's own dependency-status check
   (`runDepsStatusCheck`, visible in the reported stack trace) correctly detected the mismatch and refused
   to run the build — the exact error reported.
2. `COPY packages/connector-sdk/package.json packages/connector-sdk/README.md packages/connector-sdk/` —
   `connector-sdk` is a pure-Python package (a `pyproject.toml`, no `package.json`, ever — confirmed via
   `git log --diff-filter=A` returning nothing for that path). This COPY references a file that has never
   existed in the repository.
3. `COPY packages/shared-types/package.json packages/shared-types/package.json` — `shared-types` is a
   Milestone 1 placeholder containing only a `README.md` (its own description: "placeholder — Milestone
   2+ housekeeping"). Same bug as #2: no `package.json` has ever existed there either.

Neither `connector-sdk` nor `shared-types` is an actual dependency of `apps/web` (confirmed by grepping
`apps/web/package.json` — only `@gridkeep/ui`, `@gridkeep/security-contracts`, and `@gridkeep/config` are
listed via `workspace:*`), so both COPY lines were dead weight, not lines that needed replacing.

**Fix applied**: added `pnpm-lock.yaml` to the real COPY line, and deleted the two COPY lines referencing
files that don't exist. `apps/api` and `apps/worker`'s Dockerfiles use plain `pip install` with no
lockfile-freshness check, so they were never exposed to this bug class — confirmed by reading both, not
assumed.

**Honest limitation, unchanged**: this fix could not be verified by actually running `docker build` in
this sandbox — still no Docker daemon here. It's root-caused against the literal error text and stack
trace the user reported, and against confirmed file-existence and dependency-graph facts, not guessed at.
If a second, different failure surfaces on retry, that's expected to be reported back and fixed the same
way — this is the first time this file has ever been exercised for real.

### A fourth bug: the same class of problem, in `api.Dockerfile`, hiding the login failure's real cause

With `web`'s build fixed, the user got the stack running far enough to hit `ModuleNotFoundError: No module
named 'gridkeep_connector_sdk'` — and separately, before that, a generic "something went wrong" on login
that turned out to be the same root cause, not a credentials problem.

**Root cause**: `api.Dockerfile` built the connector SDK's editable install at `/app/connector-sdk` —
inside the same `WORKDIR /app` where `apps/api`'s own code also lands. `docker-compose.yml`'s `api` service
bind-mounts `./apps/api:/app` for the dev hot-reload loop. A bind mount replaces the *entire* target
directory with the host directory's contents at container start — so `/app/connector-sdk` (built into the
image, but not part of `./apps/api` on the host) disappears the moment the container actually runs, even
though the image built without error. `seed/bootstrap.py` imports the connector SDK, and the `api`
service's startup command is `alembic upgrade head && python -m seed.bootstrap && uvicorn main:app ...` —
so the container never reached `uvicorn` at all. That's why login returned a generic, non-`ApiError`
failure: the API was never actually up to answer the request.

`worker.Dockerfile` already avoids this exact trap — it installs the connector SDK at
`/app/packages/connector-sdk`, outside the two directories its own compose volumes mount
(`/app/apps/api`, `/app/apps/worker`). `api.Dockerfile` just didn't follow that same pattern.

**Fix applied**: moved the connector SDK's editable install to `/opt/connector-sdk`, entirely outside
`/app`, so the `./apps/api:/app` bind mount can't hide it. Same principle as `worker.Dockerfile`'s existing
layout, applied consistently.

**Honest limitation, unchanged**: same as above — root-caused from the reported error, the compose file's
actual mount configuration, and `seed/bootstrap.py`'s real import graph, not verified with a live
`docker build`/`docker compose up` in this sandbox.

### A full, proactive Docker audit — not just reacting to the next reported error

Asked explicitly to "find all the errors with Docker," rather than wait for a fifth one-at-a-time report.
This pass read every Dockerfile and the compose file line by line, cross-checked every `COPY` source and
every bind-mount target against what's actually on disk, and — new this pass — **a real Docker daemon
was actually started in this sandbox** (`dockerd`, run directly; the CLI and Compose plugin were already
present) to get real validation instead of only static reading.

**Two more real bugs found and fixed:**

5. **`NEXT_PUBLIC_API_BASE_URL` was only ever set in `docker-compose.yml`'s runtime `environment:` block**
   for the `web` service. Next.js inlines `NEXT_PUBLIC_*` variables into the client bundle at `next build`
   time — a runtime environment variable on the running container has zero effect on JS already shipped to
   the browser. This was silently masked because `lib/api-client.ts`'s fallback default
   (`http://localhost:8000`) happens to match the intended value, but it would break silently and
   confusingly the moment anyone changed that value for a real deployment. Fixed: `web.Dockerfile` now
   declares `ARG NEXT_PUBLIC_API_BASE_URL` and sets it as an `ENV` before `RUN pnpm --filter @gridkeep/web
   build`; `docker-compose.yml` passes it via `build.args` instead of `environment`.
6. **Evidence file storage (Milestone 28) defaulted to writing under `/app`** in the `api` container — the
   same directory the dev bind mount (`./apps/api:/app`) replaces wholesale at container start. Whether
   writes there succeed depends on the host directory's filesystem permissions matching the container's
   UID 1000 user, which isn't guaranteed. Fixed: added a dedicated `gridkeep_evidence_storage` named
   volume mounted at `/data/evidence-storage`, set `EVIDENCE_STORAGE_ROOT` to that path for the `api`
   service — the same separation-of-concerns pattern Postgres/Redis/MinIO's own data already uses in this
   file, rather than mixing runtime-uploaded binary files into the bind-mounted source tree.

**One structural gap closed**: **no `.dockerignore` existed anywhere in the repo.** `web.Dockerfile`'s
build stage does `COPY . .` — without a `.dockerignore`, that sends the host's actual `node_modules/`
(among other things) into the build context, which would silently overwrite the correctly Linux-built
`node_modules` from that same Dockerfile's own `deps` stage with whatever's on the host — a well-known
class of Next.js Docker failure (native `@next/swc-*` binding mismatches) that only surfaces at container
*runtime*, not at build time, making it unusually hard to diagnose after the fact. Added a repo-root
`.dockerignore` excluding `node_modules/`, `.venv/`, `.git/`, and the same build-artifact/cache directories
`.gitignore` already excludes from version control.

**What the real daemon confirmed, and what it couldn't**: `docker compose config --quiet` — full schema
and interpolation validation, no image pull required — passed with **zero errors across all seven
services**, including confirming the new `web` build-arg and `api` volume changes render exactly as
intended. Actually building any image was not possible: pulling `python:3.11-slim`, `node:20-slim`, and
even `hello-world`/`alpine:3.20` (tested directly to rule out anything image-specific) all failed
identically with the outbound proxy's `production.cloudfront.docker.com: 403 (policy denial)` — Docker
Hub registry pulls are blocked by this sandbox's network policy, the same structural category of
restriction that's blocked GitHub release downloads since Milestone 25. This is a materially more precise
finding than every prior milestone's "no Docker daemon available" — the daemon runs fine; it's outbound
registry access specifically that's walled off. That distinction is corrected here rather than left as a
stale, imprecise claim now that it's been directly re-verified.

## Next Action

Milestone 28 complete. Docker Compose is now fully audited, not just reactively patched: six real bugs
found and fixed across `web.Dockerfile`, `api.Dockerfile`, and `docker-compose.yml`, plus a `.dockerignore`
added to close a structural gap. `docker compose config --quiet` passes clean. Actually building the images
still can't be completed in this sandbox — confirmed to be a registry-pull network-policy block, not a
config or code error — so full end-to-end confirmation still depends on the user's own retry.

### A real bug from actually creating a workspace: emails carried a bare token, not a link

The user ran the full stack for real (via the manual local-dev path, not Docker — see the live-verification
note above) and onboarded a new workspace. The verification email arrived with just the raw token as text,
not a clickable link — even though `apps/web`'s `/verify-email`, `/reset-password`, and
`/accept-invitation` pages all read their token from a `?token=` query parameter and act on it
automatically (`/verify-email` even auto-submits on page load). Milestone 28's `send_email()` call sites
never built that URL; they only interpolated the bare token into the message body. A real user hitting this
on the very first live email is exactly the kind of gap live usage catches that a unit test asserting
"the token appears somewhere in the body" does not.

**Root cause**: none of `modules/tenancy/service.py` (onboarding verification), `modules/permissions/routes.py`
(invitations), or `modules/identity/routes.py` (password reset) had access to the frontend's origin — there
was no dedicated setting for it, only `cors_allow_origins` (a list meant for CORS validation, not a
canonical single URL for link-building).

**Fix**: added `app_base_url` to `core/config.py` (defaults to `http://localhost:3000`, matching the
frontend's own default), and all three email bodies now include a real clickable link
(`{app_base_url}/verify-email?token=...`, `/reset-password?token=...`, `/accept-invitation?token=...`)
instead of a bare token. `docker-compose.yml`'s `api` service gained a matching `APP_BASE_URL` environment
variable alongside its existing `NEXT_PUBLIC_API_BASE_URL` counterpart on the `web` service. Strengthened
the three existing email-content tests (`test_onboarding_sends_real_verification_email`,
`test_forgot_password_sends_real_email_for_known_account`,
`test_executive_viewer_cannot_manage_users`) to assert the real link is present, not just that the body
contains some text — locking in the fix rather than leaving it only manually verified. Full suite:
**248/248 passing**, `ruff check .` clean.
