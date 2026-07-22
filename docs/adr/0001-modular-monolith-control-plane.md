# ADR 0001: Modular Monolith for the Control Plane

## Status
Accepted (Milestone 1)

## Context
The approved architecture calls for "a modular monolith first for the control plane" with
"separately deployable workers and execution agents where isolation or scaling demands it,"
and explicitly warns against creating unnecessary microservices.

## Decision
`control-api` is a single Go binary (single `go.mod`, single deployable) internally organized
as `internal/modules/<domain>` (identity, tenancy, operators, rbac, subscriptions, auditlog,
platformadmin). Each module owns its own model, repository, service, and HTTP handler files.
Modules communicate only through:

1. Exported Go service methods (in-process calls), or
2. The shared `internal/platform/db.Store` / `internal/platform/audit` primitives.

No module reaches into another module's database tables directly; cross-module reads go
through the owning module's exported repository functions where needed (e.g.
`platformadmin` calls `subscriptions.Service.AssignEnterprisePlan` rather than writing to
`enterprise_subscriptions` itself).

`policy-engine` (Python), `worker` (Go), and later `scheduler`/`operator-agent`/
`cluster-agent`/`settlement-service` are separate deployables from day one because they have
categorically different runtime/scaling/trust requirements (Python analytics runtime, async
job processing, and — in later milestones — execution inside an operator's own trust
boundary), not because of arbitrary service-per-team boundaries.

## Consequences
- Fast local development: one binary, one migration runner, one test binary per Go module.
- A future extraction of a module into its own service is a mechanical move (the module
  already only depends on exported interfaces and shared platform primitives), not a rewrite.
- Route wiring for tenant/operator-scoped modules required flattening `Mount()` into
  `MountTopLevel()` + `Mount*Scoped()` pairs (see ADR 0002 for why) so multiple modules can
  register onto the same nested chi route group without violating chi's "Use() before Route()"
  constraint.
