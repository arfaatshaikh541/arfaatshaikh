"""Shared Celery task retry-exhaustion handling.

`Task.retry(exc=exc, ...)` re-raises the *original* exception, not
`MaxRetriesExceededError`, once retries are exhausted - a
`try/except MaxRetriesExceededError` wrapped around a `retry()` call never
catches anything on real exhaustion. Milestone 8 (docs/adr/0016) found this
the hard way: it had already shipped, unnoticed, in three of this worker's
five retrying tasks across two prior milestones, silently dying uncaught
with no error ever recorded on each one's final retry attempt. The fix at
the time was hand-written identically in all five task files: check
`self.request.retries >= self.max_retries` *before* calling `retry()`.

That fix had no automated guard against a *future* task reintroducing the
broken shape - `retry_or_finalize` below is that guard (docs/adr/0020): the
one sanctioned way to retry-then-finalize a Celery task in this codebase,
so the exhaustion check can't be forgotten or miscopied at a new call site.
"""

from collections.abc import Callable, Coroutine
from typing import Any

from app.core.logging import get_logger

from worker.async_utils import run_db_task

logger = get_logger("gridkeep.worker.retry")


def default_backoff(retries: int) -> float:
    """The exponential-backoff-capped-at-60s formula this worker's tasks
    have used since Milestone 2. Not required by `retry_or_finalize` - a
    task may compute its own `countdown` instead - but shared here so the
    formula only needs to change in one place if it ever does."""
    return min(60.0, 5.0 * (2**retries))


def retry_or_finalize(
    task: Any,
    *,
    exc: BaseException | None,
    finalize: Callable[[], Coroutine[Any, Any, None]],
    countdown: float,
    task_name: str,
    task_id: str,
) -> None:
    """Either re-raises `exc` as a Celery retry, or - once `task` has used
    up its retry budget - runs `finalize()` and returns normally.

    `finalize` must be a zero-argument callable returning a fresh coroutine
    (e.g. a `lambda`), not an already-created coroutine object: it is only
    ever invoked on the exhausted path, and a coroutine created but never
    awaited on the retry path would otherwise leak a runtime warning.
    `finalize`'s coroutine is expected to mark the domain record (campaign
    task, enrichment, export, csv import, integration delivery) as failed
    with a real error - that write is this task's actual terminal outcome,
    so this function deliberately does not re-raise anything afterwards;
    Celery will see the task complete without error.

    Must be called from inside the task's own `except` block; the caller
    does not need to write `raise` in front of the call - this function
    raises internally on the retry path.

    Caller's note: `except SomeError as exc:` implicitly unbinds `exc` when
    the block exits, so `finalize`'s lambda must not reference `exc`
    directly (a valid closure at the moment it's created, since it runs
    before the block exits, but flagged - correctly, as a real footgun in
    general - by ruff's F821). Assign `exc` to a plain local variable first
    (e.g. `error = exc`) and close over that name instead.
    """
    if task.request.retries >= task.max_retries:
        logger.warning(
            "task_retries_exhausted",
            task_name=task_name,
            task_id=task_id,
            error=str(exc) if exc is not None else None,
            error_type=type(exc).__name__ if exc is not None else None,
        )
        run_db_task(finalize())
        return
    if exc is None:
        raise task.retry(countdown=countdown) from None
    raise task.retry(exc=exc, countdown=countdown) from exc
