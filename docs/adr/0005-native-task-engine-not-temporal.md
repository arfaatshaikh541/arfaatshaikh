# ADR 0005: Durable task engine is native SQLite, not Temporal, for now

## Status
Implemented (`core/src/aura_core/tasks/`)

## Context
`docs/architecture/11-technology-stack.md` recommends Temporal for durable
workflow execution. Standing up a real Temporal deployment (server +
worker SDK) is a legitimate long-term choice but adds an operational
dependency (a service to run, monitor, and secure) disproportionate to
this stage, mirroring the reasoning in ADR 0004 for the Policy Engine.

## Decision
Implement task durability natively over SQLite: a `tasks` table with
explicit states (QUEUED/RUNNING/WAITING/BLOCKED/NEEDS_APPROVAL/RETRYING/
COMPLETED/FAILED/CANCELLED), lease-based claiming with expiry-driven
recovery, dependency-gated promotion from BLOCKED to QUEUED, and
backoff-scheduled retries. `TaskEngine` is the only interface calling
code depends on.

## Consequences
- **Positive**: zero new operational dependency; genuinely testable in
  this environment (and any environment) without a running server;
  crash recovery (`reap_expired_leases`) is real and tested, not
  theoretical.
- **Negative**: no built-in workflow *history replay*, versioning, or
  cross-language worker support the way Temporal provides; a single
  SQLite file is a single point of contention under heavy concurrent
  load (acceptable at single-owner scale, revisit if it isn't).

## Migration path
`TaskEngine`'s method surface (`enqueue`, `claim_next`, `complete`,
`fail`, `cancel`, `mark_needs_approval`/`resume_from_approval`,
`reap_expired_leases`) is the contract calling code (the Executive loop,
connector handlers) depends on. Swapping the backend to Temporal later
means reimplementing this surface against Temporal's SDK — workflow
*logic* built against this interface does not need to change.
