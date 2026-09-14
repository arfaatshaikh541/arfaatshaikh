# Milestone 12 Unit 2: Resilient Synchronization Transport

This unit adds the portable contracts for scheduled synchronization, bounded transfer batches, replay-resistant chunks, retry classification, dead-letter containment, deterministic progress reconciliation, and safe checkpoint advancement.

## Safety invariants

- Only trusted nodes may be scheduled.
- Schedules are bounded to 5 minutes through 7 days and at most four concurrent runs.
- Transfer chunks are capped at 1,000 items and 10 MiB.
- Chunk idempotency keys prevent duplicate acceptance within a batch.
- Only network errors, HTTP 429, and HTTP 5xx responses are retryable.
- Retry budgets are capped at eight attempts.
- Permanent failures and exhausted retries enter a dead-letter state.
- Checkpoints cannot advance while conflicts or dead letters remain.

## Portable acceptance

The implemented service layer is deterministic and side-effect free. Live Celery workers, Redis locks, outbound HTTP transport, object storage, and production scheduling are intentionally not claimed by this unit.
