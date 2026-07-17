# ADR-0009: Per-task event loop isolation for the Celery worker's async clients

## Status
Accepted (discovered and fixed during Milestone 2 implementation).

## Context
The worker's Celery tasks are synchronous functions (Celery does not run
an async event loop itself) that each call `asyncio.run(...)` once to
execute the actual async domain logic - a fresh event loop is created,
run to completion, and closed, on every single task invocation.

Both of the async clients the worker's domain logic depends on -
SQLAlchemy's async engine (`app.core.db.engine`, using the `asyncpg`
driver) and `redis-py`'s async client (`app.core.rate_limit`'s module-level
`_redis` singleton) - cache their underlying connections at *module*
scope, shared across every task the same forked worker process runs. Both
drivers bind a connection to the event loop that created it.

The first time a worker process ran two campaign-task pages back to back,
the second page's task crashed with `RuntimeError: Task ... got Future
... attached to a different loop` (from asyncpg) and, once that was
fixed, `RuntimeError: Event loop is closed` (from redis-py) - both because
the second task's `asyncio.run()` call created a brand new loop, but the
connection pool handed back a connection that belonged to the *first*
task's now-closed loop.

This is easy to reintroduce: it only manifests once a worker process
handles a second task, so a manual test that restarts the worker between
every task run (or only ever runs one task per process lifetime) will
never observe it - which is exactly how it slipped through initial
implementation and was only caught by a real end-to-end test that let the
same worker process run a multi-page campaign to completion.

## Decision
- `worker.async_utils.run_db_task(coro)` wraps every Celery task's
  `asyncio.run(...)` call. After the wrapped coroutine finishes (success
  or exception), it calls `await engine.dispose()` (closing every pooled
  SQLAlchemy connection) and `await app.core.rate_limit.reset_redis_connection()`
  (closing and forgetting the cached redis-py client).
- Because Celery's prefork workers process exactly one task to completion
  before starting the next in a given child process, this teardown is
  safe: the next `asyncio.run()` call is guaranteed to open fresh
  connections bound to its own new loop, never a stale one.
- `worker.campaign_tasks.run_campaign_task` and
  `worker.tasks.expire_stale_reservations` both use `run_db_task` instead
  of calling `asyncio.run` directly - there is no third way to reach the
  database or Redis from a worker task.
- The API process is unaffected and needs no equivalent: it serves every
  request on one long-lived event loop (uvicorn's), so its connections are
  never handed across a loop boundary.

## Consequences
- Any new Celery task added in a later milestone must go through
  `run_db_task`, not a bare `asyncio.run(...)` - a bare call will work in
  isolation and in single-task manual testing, then fail exactly like this
  bug did the moment the same worker process handles a second task.
- `apps/worker/tests/test_campaign_tasks.py` exercises multi-task chains
  directly (not through a live Celery broker), which would have caught
  this regression if it existed when that suite was written; the fix
  predates the suite, since it was found via manual live-dispatch testing
  first (see the Milestone 2 session transcript).
- This is the same class of bug as ADR-0007 (RLS-ordering): a resource
  scoped more broadly than its actual safe lifetime, only surfacing under
  a usage pattern (a second call in the same process) that isn't obvious
  from reading any single call site in isolation.
