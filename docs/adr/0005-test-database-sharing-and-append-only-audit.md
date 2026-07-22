# ADR 0005: Shared Test Database Requires Sequential Package Execution

## Status
Accepted (Milestone 1)

## Context
`go test ./...` runs each package's tests in a separate process, and by default runs multiple
packages' test binaries *concurrently*. All of this project's Go integration tests point at
one physical database (`gridkeep_test`, `TEST_DATABASE_URL`) and each test truncates every
relevant table at start (`internal/testutil.NewStore`). Running `internal/app` and
`internal/platform/audit` tests concurrently against that shared database produced real
PostgreSQL deadlocks and one flaky false-negative (`TestAuditEvents_AreAppendOnly` appeared to
fail only when interleaved with another package's truncate).

## Decision
Go tests in this repository must be run with `-p 1` (sequential package execution):

```
go test -p 1 ./...
```

This is codified in `.github/workflows/ci.yml` and `docs/operations/local-development.md`.
Tests within a single package still run sequentially by default (no `t.Parallel()` is used),
so this only affects cross-package scheduling.

## Alternatives considered
- Per-package logical schemas/databases: more correct isolation, deferred as unnecessary
  complexity at Milestone 1 test-suite size; revisit if `-p 1` makes CI too slow later.
- Mocking Postgres: rejected outright -- RLS policies, triggers (audit append-only
  enforcement), and constraints (dual-control CHECK on `support_access_grants`) are
  first-class parts of the system under test and cannot be meaningfully mocked.

## Consequences
Test suite runtime is bounded by total sequential time across packages rather than
wall-clock-parallel time; at Milestone 1 scale (well under 5 seconds total) this is not a
practical concern.
