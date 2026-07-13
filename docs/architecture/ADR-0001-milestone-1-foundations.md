# ADR-0001: Milestone 1 Foundations

Status: Accepted
Date: 2026-07-13

## Context

We are building a multi-tenant Lead-to-Booking Automation SaaS for UAE
professional-service businesses (auditors, accountants, tax consultants,
business-setup companies, corporate service providers, consultancies). The
platform must be sold to many tenants, each configuring their own business
identity, users, roles, pipeline, and workflows without code changes.

Milestone 1 lays the foundation everything else builds on: the monorepo,
local dev environment, multi-tenancy data model, authentication, RBAC, and
tenant settings. Every later milestone (leads, pipeline, scoring,
assignment, booking, workflows, reporting) depends on tenant isolation and
auth being correct, so we treat those as the highest-risk, most-tested part
of the system.

## Decisions

1. **Monorepo with apps/packages/infrastructure/docs split.** `apps/api`
   (FastAPI), `apps/worker` (Celery), `apps/web` (Next.js) are independently
   deployable. `packages/shared-types`, `packages/config`, `packages/ui` hold
   code shared across frontend surfaces. This keeps the platform
   hosting-agnostic (any container host, not one PaaS).

2. **PostgreSQL as system of record, normalized schema.** Tenant-owned
   entities are real tables with `tenant_id` foreign keys, not JSON blobs.
   JSON columns are used only where the schema is genuinely tenant-defined
   and unbounded (e.g. business hours structure, plan feature flags),
   never for core relational data like users, roles, or memberships.

3. **Tenant isolation is enforced in the backend, in one place.** Every
   repository method that reads or writes tenant-owned data requires a
   verified `tenant_id` obtained from a server-side dependency
   (`get_current_membership`), never from a client-supplied body/query
   field alone. See `tenant-isolation-strategy.md`.

4. **Authentication: server-verified sessions with short-lived JWT access
   tokens + rotating opaque refresh tokens, both in `HttpOnly` cookies.**
   No client-side "trust the JWT claims for authorization" pattern beyond
   identifying the user. See `authentication-strategy.md`.

5. **RBAC: permission catalog is global, roles are tenant-scoped rows
   seeded from defaults.** Each tenant gets its own copy of default roles
   (Owner, Administrator, Manager, Sales Agent, Support Agent, Viewer) so
   tenants can rename/adjust without affecting other tenants, while a
   platform-level `is_platform_super_admin` flag on `User` (not a tenant
   role) grants cross-tenant platform administration, fully audit-logged.

6. **Repository/service layered architecture in the API.** Routers only
   handle HTTP concerns; services hold business logic; repositories hold
   SQLAlchemy queries scoped by tenant. This keeps tenant-scoping
   consistent and testable in one layer instead of scattered across
   routers.

7. **Alembic migrations are the only way schema changes ship.** No
   `create_all()` in application startup for anything but the test DB
   bootstrap.

8. **Celery + Redis for background work**, wired up in Milestone 1 (health
   task + email-sending task) so later milestones (reminders, workflows,
   exports) plug into an already-working worker rather than retrofitting
   one.

9. **Docker Compose for local dev**: Postgres, Redis, api, worker, web,
   Mailhog (local mail capture so email flows are testable without a real
   provider). No cloud vendor lock-in — all services are open-source /
   self-hostable images.

## Consequences

- Every new tenant-owned table added in later milestones must follow the
  same `tenant_id`-scoped repository pattern established here, and must
  add an isolation test following the pattern in
  `apps/api/tests/test_tenant_isolation.py`.
- Access tokens are intentionally minimal (user id + session id) so
  authorization data is never stale; this costs one extra DB lookup per
  request, which is acceptable given the low request volume of an
  operational CRM versus the security benefit of instant revocation.
- Because roles are per-tenant rows, permission checks always join through
  `memberships -> roles -> role_permissions -> permissions` for the
  *verified* tenant context, never a cached/global role name string.

## Alternatives Considered

- **Row-Level Security (Postgres RLS) instead of application-level
  scoping.** Rejected for v1: RLS adds real defense-in-depth but requires
  every connection to `SET app.tenant_id` correctly and doesn't remove the
  need for repository-level scoping (it's a second control, not a
  replacement, and the async connection-pooling pattern with RLS is easy
  to get subtly wrong). We record this as a documented follow-up
  hardening item in `docs/security/` rather than doing it half-right now.
- **Single shared roles table with tenant_id nullable "templates".**
  Rejected: it complicates the common-case query (list a tenant's roles)
  for a benefit (deduping identical default roles) that doesn't matter at
  SaaS scale.
- **Stateless JWT-only auth with no server session record.** Rejected:
  cannot support "session revocation" or refresh-token-reuse breach
  detection, both explicitly required.
