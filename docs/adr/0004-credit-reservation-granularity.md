# ADR-0004: Credit reservation granularity (campaign-level, deferred to Milestone 2)

## Status
Accepted (Milestone 1 approval item #6).

## Context
The architecture calls for reserving estimated campaign cost before work
starts. Milestone 1 has no campaign engine yet - only the credit-ledger
foundation (wallet, transaction, reservation models and the
reserve/commit/release service).

## Decision
Milestone 1 implements the reservation primitive generically
(`app.modules.usage.services.reserve_credits` /
`commit_reservation` / `release_reservation`), tenant-scoped and
concurrency-safe (`SELECT ... FOR UPDATE` on the wallet row), but nothing
in Milestone 1 calls it end-to-end for a real workflow. Task-level
reservation granularity (one reservation per campaign task rather than
one per whole campaign) is a Milestone 2 decision, made when the campaign
task-fan-out design is built.

## Consequences
- Milestone 1's tests exercise the primitive directly
  (`tests/test_credit_wallet.py`), not via an HTTP-facing campaign flow.
- The worker's only real scheduled job in Milestone 1,
  `expire_stale_reservations`, proves the reservation lifecycle works
  end-to-end through Celery/Redis even though nothing yet creates
  reservations through user action.
