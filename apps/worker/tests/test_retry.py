"""Tests for `worker.retry.retry_or_finalize` - the shared Celery
retry-exhaustion helper (Milestone 12, docs/adr/0020) that replaced the
identical hand-written `if self.request.retries >= self.max_retries`
check duplicated across all five of this worker's retrying tasks. These
exercise `retry_or_finalize` directly with a minimal fake Celery task
double, independent of any specific task's own domain logic - each real
task's own retry-exhaustion behavior is still covered by its own test
file (e.g. `test_integration_tasks.py`'s `test_celery_wrapper_finalizes_
as_failed_once_retries_are_exhausted`), which now exercises this same
shared function via that task's real `except` block.

Written as plain (non-async) functions, deliberately: `retry_or_finalize`
calls `worker.async_utils.run_db_task` (which wraps `asyncio.run`) on the
finalize path, and `asyncio.run` cannot be called from inside a running
event loop - exactly what an `async def` pytest-asyncio test would be.
The finalize-path tests monkeypatch `worker.retry.run_db_task` with the
same synchronous `coro.send(None)` driver `test_integration_tasks.py`
uses, rather than the real `run_db_task` - `run_db_task`'s own
`asyncio.run`/engine-dispose/redis-reset plumbing is a separate concern
already exercised end-to-end by every task's own real Celery-wrapped
test (e.g. `test_integration_tasks.py`'s `test_celery_wrapper_finalizes_
as_failed_once_retries_are_exhausted`); what's under test here is purely
`retry_or_finalize`'s own retry-vs-finalize branching.
"""

from worker import retry as retry_module
from worker.retry import default_backoff, retry_or_finalize


def _sync_run_db_task(coro):
    try:
        coro.send(None)
    except StopIteration as si:
        return si.value
    raise AssertionError("stub coroutine unexpectedly suspended on a real await")


class _FakeRequest:
    def __init__(self, retries: int) -> None:
        self.retries = retries


class _FakeRetry(Exception):
    """Stands in for Celery's own `Retry` exception - `retry_or_finalize`
    raises whatever `task.retry(...)` returns, so it doesn't matter that
    this fake doesn't raise internally the way real Celery's `Task.retry`
    does; the `raise` in `retry_or_finalize`'s own code is what's under
    test here."""

    def __init__(self, exc: BaseException | None, countdown: float) -> None:
        super().__init__("retry")
        self.exc = exc
        self.countdown = countdown


class _FakeTask:
    def __init__(self, retries: int, max_retries: int) -> None:
        self.request = _FakeRequest(retries)
        self.max_retries = max_retries
        self.retry_calls: list[tuple[BaseException | None, float]] = []

    def retry(self, *, exc: BaseException | None = None, countdown: float = 0) -> _FakeRetry:
        self.retry_calls.append((exc, countdown))
        return _FakeRetry(exc, countdown)


def test_raises_retry_with_exc_when_budget_remains() -> None:
    task = _FakeTask(retries=1, max_retries=4)
    exc = ValueError("transient")
    finalize_calls: list[str] = []

    async def finalize() -> None:
        finalize_calls.append("called")

    try:
        retry_or_finalize(task, exc=exc, finalize=finalize, countdown=10, task_name="t", task_id="1")
        raise AssertionError("expected a retry exception to be raised")
    except _FakeRetry as raised:
        assert raised.exc is exc
        assert raised.countdown == 10

    assert task.retry_calls == [(exc, 10)]
    assert finalize_calls == []  # never runs while retries remain


def test_raises_retry_without_exc_when_no_exc_supplied() -> None:
    """The `_SlotUnavailable` shape: an internal control-flow exception
    with nothing meaningful to hand Celery as `exc=`."""
    task = _FakeTask(retries=0, max_retries=8)

    async def finalize() -> None:
        raise AssertionError("must not run while retries remain")

    try:
        retry_or_finalize(task, exc=None, finalize=finalize, countdown=15, task_name="t", task_id="1")
        raise AssertionError("expected a retry exception to be raised")
    except _FakeRetry as raised:
        assert raised.exc is None
        assert raised.countdown == 15

    assert task.retry_calls == [(None, 15)]


def test_finalizes_and_does_not_raise_once_retries_are_exhausted(monkeypatch) -> None:
    monkeypatch.setattr(retry_module, "run_db_task", _sync_run_db_task)
    task = _FakeTask(retries=4, max_retries=4)
    exc = RuntimeError("permanent by exhaustion")
    finalize_calls: list[str] = []

    async def finalize() -> None:
        finalize_calls.append("called")

    retry_or_finalize(
        task, exc=exc, finalize=finalize, countdown=30, task_name="t", task_id="1"
    )  # must not raise

    assert finalize_calls == ["called"]
    assert task.retry_calls == []  # retry() must never be called once exhausted


def test_finalizes_when_retries_exceed_max_retries(monkeypatch) -> None:
    """Defensive: `>=`, not `==` - a task somehow delivered with a retry
    count already past its budget must still finalize rather than call
    `retry()` again."""
    monkeypatch.setattr(retry_module, "run_db_task", _sync_run_db_task)
    task = _FakeTask(retries=9, max_retries=4)
    finalize_calls: list[str] = []

    async def finalize() -> None:
        finalize_calls.append("called")

    retry_or_finalize(task, exc=None, finalize=finalize, countdown=5, task_name="t", task_id="1")

    assert finalize_calls == ["called"]


def test_default_backoff_is_exponential_capped_at_60() -> None:
    assert default_backoff(0) == 5.0
    assert default_backoff(1) == 10.0
    assert default_backoff(2) == 20.0
    assert default_backoff(3) == 40.0
    assert default_backoff(4) == 60.0  # would be 80 uncapped
    assert default_backoff(10) == 60.0
