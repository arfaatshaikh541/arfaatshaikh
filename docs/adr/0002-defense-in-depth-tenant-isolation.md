# ADR 0002: Two-Layer Tenant/Operator Isolation (Application + RLS)

## Status
Accepted (Milestone 1)

## Context
Rule #19/#20 of the project's working rules require that tenant/operator identifiers
supplied by the browser are never trusted, and that identity/tenancy/operator boundaries are
enforced in the backend. A single layer of enforcement (e.g. "always add `WHERE tenant_id =
?` in application code") is one missed `WHERE` clause away from a cross-tenant leak.

## Decision
Every tenant-owned and operator-owned table (`enterprise_memberships`, `operator_memberships`,
`invitations`, `enterprise_subscriptions`, `operator_subscriptions`, `audit_events`) has
PostgreSQL Row-Level Security **enabled and forced**, with policies keyed on session GUCs
(`app.tenant_id`, `app.operator_id`, `app.platform_bypass`) that `internal/platform/db.Store.BeginScoped`
sets via `SET LOCAL` (transaction-scoped, never leaks between requests or pooled connections).

`internal/modules/rbac` middleware (`RequireEnterprisePermission`, `RequireEnterpriseMembership`,
and their operator equivalents) resolves the tenant/operator scope from the caller's session +
membership rows -- never from the URL path segment alone -- and opens the scoped transaction
*before* running the membership/permission query, so RLS is exercised as part of every
authorization decision, not bypassed by it.

A request handler receives the already-scoped transaction via `rbac.TxFromContext` and is
structurally unable to query outside the scope the middleware established (no repository
function accepts an arbitrary/unscoped connection for these tables).

## Consequences
- Verified directly (see `internal/platform/audit/audit_test.go` `TestAuditEvents_HiddenWithoutTenantOrPlatformScope`):
  a raw `Pool.QueryRow` with no scope GUC set cannot see a row that was just inserted and
  committed, proving RLS -- not just the application layer -- gates visibility.
- Verified via `internal/app` integration tests (`TestCrossTenantIsolationDenied`,
  `TestCrossOperatorIsolationDenied`): a user with no membership is denied at both the
  membership-check layer and the permission-check layer.
- Cost: every tenant/operator-scoped request opens its own transaction (one connection
  checkout per request). Acceptable at Milestone 1 control-plane traffic volumes; revisit if
  connection-pool exhaustion becomes an issue at higher milestones' scale.
