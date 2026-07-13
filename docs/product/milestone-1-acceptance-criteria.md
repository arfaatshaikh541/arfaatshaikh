# Milestone 1 — Acceptance Criteria

Milestone 1 scope: monorepo, Docker Compose, authentication, multi-tenancy,
users, roles, tenant settings, database migrations, seed data, tests.

A criterion is "done" only when it is exercised by an automated test or is
directly observable by running the stack locally — not by inspection of
code alone.

## Monorepo & Local Dev

- [ ] `apps/{api,worker,web}`, `packages/{shared-types,config,ui}`,
      `infrastructure/{docker,scripts}`, `docs/{architecture,api,deployment,
      security,product}` exist per `repository-structure.md`.
- [ ] `docker compose up --build` brings up postgres, redis, api, worker,
      web, mailhog with healthy healthchecks.
- [ ] `GET /api/health` returns `200` with DB + Redis connectivity status.

## Multi-Tenancy

- [ ] Creating a tenant creates `Tenant`, `TenantSettings` (defaults), and
      seeds the six default `roles` with correct `role_permissions`.
- [ ] A user can hold memberships in two different tenants and switch
      between them (`X-Tenant-Id` header / active-tenant selector).
- [ ] A request scoped to Tenant A cannot read, update, or delete a
      resource belonging to Tenant B — enforced and covered by
      `test_tenant_isolation.py`.
- [ ] Suspended and archived tenants: members of a suspended/archived
      tenant are denied access to that tenant's context (`403`), while a
      platform super admin can still view (read-only) for support purposes,
      with the access written to `audit_logs`.
- [ ] Platform super admin actions against tenant data are logged to
      `audit_logs` with actor, tenant, event type, and timestamp.

## Authentication

- [ ] Login with correct credentials sets `access_token` + `refresh_token`
      + `csrf_token` cookies and returns the user + tenant memberships.
- [ ] Login with incorrect credentials returns a generic error, and after
      5 failed attempts in 15 minutes from the same email+IP returns `429`.
- [ ] `POST /api/auth/refresh` rotates the refresh token; presenting an
      already-rotated (reused) refresh token revokes the full session
      family.
- [ ] `POST /api/auth/logout` revokes the current session; subsequent
      refresh attempts with that token fail.
- [ ] Password reset flow: request → emailed token (visible in Mailhog
      locally) → reset → all prior sessions revoked.
- [ ] Email verification token is issued on invitation acceptance and
      consumable exactly once.
- [ ] Passwords are hashed with Argon2id; no endpoint ever returns a
      password hash, token, or secret in a response body or log line.

## RBAC

- [ ] Each default role's permission set matches `authorization-model.md`.
- [ ] `test_authorization.py` parametrizes protected endpoints × roles and
      passes for all combinations.
- [ ] A user without `users.manage` cannot invite/deactivate users
      (`403`); a user without `settings.manage` cannot update tenant
      settings (`403`).

## Tenant Settings

- [ ] Tenant admin can update business name, legal name, logo URL, brand
      colors, contact info, business hours, timezone (default
      `Asia/Dubai`), currency (default `AED`), and privacy text via API and
      see it reflected on `GET /api/tenants/me/settings`.
- [ ] Settings changes are validated (e.g. hex colors, IANA timezone,
      ISO currency code) and rejected with clear `422` errors otherwise.

## Database & Migrations

- [ ] `alembic upgrade head` runs cleanly against an empty database.
- [ ] `alembic downgrade base` then `upgrade head` again succeeds
      (round-trip safety) in CI.
- [ ] No application table relies on `Base.metadata.create_all()` outside
      of the test bootstrap fixture.

## Seed Data

- [ ] `python -m app.seed` is idempotent (safe to run twice) and produces
      the documented platform super admin and Rafana Advisory Demo tenant
      with Owner/Manager/Sales Agent users.

## Tests, Build & Quality Gates

- [ ] `ruff check` and `ruff format --check` pass on `apps/api` and
      `apps/worker`.
- [ ] `mypy` (or equivalent strict type check) passes on `apps/api`.
- [ ] `pytest` passes on `apps/api` including unit, integration,
      tenant-isolation, and authorization suites.
- [ ] `pnpm lint`, `pnpm typecheck`, and `pnpm test` pass on `apps/web`.
- [ ] `pnpm build` (production Next.js build) succeeds.
- [ ] CI workflow (`.github/workflows/ci.yml`) runs all of the above on
      every push/PR.

## Explicit Non-Goals for Milestone 1 (tracked, not silently dropped)

- Leads, pipeline, scoring, assignment, booking, workflows, reporting —
  Milestones 2–6.
- TOTP two-factor enrollment/verification endpoints (schema only in M1).
- Postgres Row-Level Security (documented as a future hardening layer on
  top of the application-level tenant scoping already enforced).
- Real WhatsApp/SMS provider integration (interfaces reserved, no adapter
  shipped until a later milestone; email uses SMTP/Mailhog locally and is
  the only "real" provider in v1).
