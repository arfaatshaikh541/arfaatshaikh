# Architecture overview

Multi-tenant, modular-monolith SaaS platform for UAE professional-service
businesses. This document captures the durable architecture decisions
made before Milestone 1 and updated as later milestones land. For
current build status, see `docs/product/project-status.md`.

## System shape

```
Browser (tenant staff / platform admin / public visitor)
        │  HTTPS
        ▼
Next.js (App Router) — client components call the API directly
        │  HTTPS (CORS-protected, session-cookie authenticated)
        ▼
FastAPI — auth → tenant context → permission check → entitlement check → usage check → handler
        │
        ├──▶ PostgreSQL (RLS + tenant_id scoping)
        ├──▶ Redis (sessions/rate-limit/download-token cache, Celery broker/result backend)
        └──▶ S3-compatible object storage (signed URLs, tenant-prefixed paths)
```

One platform, many modules, per-tenant entitlements — not one codebase
per customer. See "Subscription and entitlement strategy" below.

## Modular-monolith architecture

Single deployable backend (`apps/api`), organised into modules under
`app/modules/<name>/` — each with `models.py`, `repository.py`,
`service.py`, `routes.py` (and `schemas.py` where the module has its own
request/response shapes). Modules communicate through each other's
`service.py` functions, never through another module's `repository.py`
or ORM `relationship()` — cross-module references are plain foreign-key
columns, joined explicitly where needed. This keeps the modules loosely
coupled enough to extract into a separate service later without a
rewrite, without paying microservice operational cost now.

Shared, module-agnostic code lives in `app/core/` (config, DB session,
security, error handling, logging, rate limiting, storage) and
`app/dependencies/` (auth, tenant-context, permission, entitlement
dependencies used by every module's routes).

`apps/worker` (Celery) imports the same `app.modules` package as the API
— background tasks are thin wrappers calling the same service-layer
functions, no duplicated business logic.

## Major architecture decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Modular monolith, single Postgres DB, `tenant_id` column on every tenant-owned table | Avoids premature microservice/DB-per-tenant cost |
| D2 | Authorization is backend-enforced always; RLS is defence-in-depth, not primary | Frontend/RLS-only trust is a common SaaS breach vector |
| D3 | Session-based auth via HTTP-only cookies + server-side session store, not stateless JWT | Enables instant session revocation |
| D4 | Entitlements modeled as a layer separate from billing state | Support/platform-admin can grant trials/overrides without touching billing |
| D5 | Alembic migrations, no ORM-driven auto-DDL in production | Predictable, reviewable schema changes |
| D6 | Celery + Redis for background jobs | Mature retry/scheduling tooling |
| D7 | S3-compatible storage via an adapter interface, MinIO locally | No cloud lock-in |
| D8 | Next.js client components call the API directly (not proxied through a Next.js server layer) | Simpler cookie handling; no secrets ever live in these calls anyway (see D2) |
| D9 | Entitlement/permission logic is data-driven, never hardcoded in frontend components or backend conditionals | Required for a sellable, configurable product |
| D10 | UUID primary keys, UTC timestamps, Asia/Dubai default tenant timezone, AED default currency | UAE-market defaults |

## Tenant-isolation strategy

- Tenant context is derived exclusively from the authenticated session's
  `active_tenant_id` plus a live `memberships` row — never from a
  client-supplied `tenant_id`.
- Every tenant-owned repository query filters by `tenant_id` from the
  resolved `TenantContext`.
- PostgreSQL row-level security is enabled and `FORCE`d on every
  tenant-owned table as defence-in-depth. See `docs/database/README.md`
  for the exact policies — including the two "chicken-and-egg" cases
  (reading your own tenant list before one is selected; a public
  lead-capture token establishing tenant context before any row is
  touched) that required extra policy design, found and fixed via this
  project's own end-to-end testing during Milestone 1 and 2.
- Automated tests cover cross-tenant reads/writes for every module.

## PostgreSQL RLS strategy

Two Postgres roles, provisioned identically in every environment
(`infrastructure/docker/postgres/init-roles.sh`):
- `app_migrator` — `NOSUPERUSER BYPASSRLS`, owns the schema, used only
  by Alembic.
- `app_runtime` — `NOSUPERUSER NOBYPASSRLS`, used by the API and worker
  at request time, subject to every RLS policy.

RLS policies key off three Postgres session-local GUCs
(`app.current_tenant_id`, `app.is_platform_admin`, `app.current_user_id`),
set via `set_config(..., is_local=true)` — transaction-scoped, never
leaking across pooled connections, never built from raw string
interpolation. See `app/core/db.py` and `docs/database/README.md`.

## Authentication & authorisation strategy

Argon2id password hashing, opaque session tokens stored only as a
SHA-256 hash server-side, HTTP-only/SameSite=Lax/Secure-in-production
cookies, Redis-backed login throttling, generic error responses (no
account enumeration). Two independent, backend-enforced axes on every
protected route: RBAC (`require_permission`) and entitlements
(`require_module`/`require_feature`/`check_usage_limit`). Platform
permissions are structurally excluded from tenant role management — see
`app/modules/permissions/catalog.py`.

## Subscription and entitlement strategy

`resolve_entitlements()` (`app/modules/entitlements/service.py`) is the
single source of truth: plan → add-ons → tenant-specific overrides
(overrides always win), consulted by both backend enforcement
dependencies and the `/me/entitlements` endpoint the frontend polls for
UI hints. Usage limits use `SELECT ... FOR UPDATE` for concurrency
safety. See `app/db/seed/catalog.py` for the full module/feature/plan
catalog.

## Storage architecture

`StorageAdapter` interface (`app/core/storage.py`) with a
`LocalDiskAdapter` (dev — signed downloads via a random Redis-backed
token redeemed at `GET /api/files/{token}`) and an `S3Adapter`
(production — real S3 presigned URLs, any S3-compatible provider).
Storage keys are tenant- and entity-namespaced and UUID-randomised,
never sequential or guessable.

## Local development & deployment

See the root `README.md` for local dev setup and
`infrastructure/deployment/README.md` for migrations, connection
pooling, backups, restore testing, and CI/CD.

## Security

See `docs/security/README.md` for the full, currently-implemented
control list and known gaps — kept in sync with each milestone rather
than written once and left stale.
