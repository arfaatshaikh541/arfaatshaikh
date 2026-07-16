# GRIDKEEP Cyber OS — Project Status

Last updated: 2026-07-16 (Milestone 8 implementation)

## Current Milestone

**Milestone 8: Executive Reporting** — implementation complete, pending your review and explicit
approval to proceed to Milestone 9. Milestones 1 (Secure SaaS Core), 2 (Integration SDK and Asset
Graph), 3 (Findings and Risk Engine), 4 (Cyber Autopilot), 5 (Incident Response), 6 (Backup and
Ransomware Resilience), and 7 (Compliance and Evidence) are complete and merged; their sections below
are preserved as-is.

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

## Pending Approvals

- This Milestone 8 implementation is ready for your review. Nothing further is pending my side — the
  acceptance checklist above is complete, tests pass, and known gaps are documented rather than hidden.
- Recommend explicit review of the `reports.view` cross-cutting-permission decision (see Architecture
  Decisions and Unresolved Risks) — it's the interpretive core of this milestone and shapes how any
  future report-like surface should be gated.

## Next Action

Awaiting your review. Once you're satisfied, send **`APPROVE MILESTONE 9`** to begin the next milestone.
