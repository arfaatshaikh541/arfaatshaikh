from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aura_core.tasks import TaskEngine, TaskNotFound
import pytest


def make_engine(tmp_path) -> TaskEngine:
    return TaskEngine(f"sqlite:///{tmp_path}/tasks.db")


def test_enqueue_and_claim_happy_path(tmp_path):
    engine = make_engine(tmp_path)
    task = engine.enqueue("send_email", {"to": "ahmed@example.com"})
    assert task.status == "QUEUED"

    claimed = engine.claim_next("worker-1")
    assert claimed is not None
    assert claimed.id == task.id
    assert claimed.attempts == 1

    # Claimed task is now RUNNING and not claimable again.
    assert engine.claim_next("worker-2") is None

    engine.complete(task.id, {"message_id": "abc"})
    record = engine.get(task.id)
    assert record.status == "COMPLETED"
    assert record.result_json == '{"message_id": "abc"}'


def test_dependent_task_stays_blocked_until_dependency_completes(tmp_path):
    engine = make_engine(tmp_path)
    upstream = engine.enqueue("research", {})
    downstream = engine.enqueue("draft_email", {}, depends_on=[upstream.id])

    assert engine.get(downstream.id).status == "BLOCKED"
    assert engine.claim_next("worker-1").id == upstream.id  # only the ready one

    engine.complete(upstream.id, {})
    promoted = engine.promote_ready_blocked_tasks()
    assert promoted == 1
    assert engine.get(downstream.id).status == "QUEUED"

    claimed = engine.claim_next("worker-1")
    assert claimed.id == downstream.id


def test_failure_retries_with_backoff_then_gives_up(tmp_path):
    engine = make_engine(tmp_path)
    task = engine.enqueue("flaky_call", {}, max_attempts=2)

    engine.claim_next("worker-1")
    status = engine.fail(task.id, "connection reset", backoff_seconds=0)
    assert status == "RETRYING"
    assert engine.get(task.id).attempts == 1

    engine.claim_next("worker-1")
    status = engine.fail(task.id, "connection reset again", backoff_seconds=0)
    assert status == "FAILED"
    assert engine.get(task.id).error == "connection reset again"


def test_backoff_delays_the_retry_run_at(tmp_path):
    engine = make_engine(tmp_path)
    task = engine.enqueue("flaky_call", {}, max_attempts=3)
    engine.claim_next("worker-1")
    engine.fail(task.id, "boom", backoff_seconds=3600)  # far in the future

    assert engine.claim_next("worker-2") is None  # not ready yet
    record = engine.get(task.id)
    assert record.status == "RETRYING"
    # SQLite doesn't round-trip tzinfo through SQLAlchemy's DateTime(timezone=True)
    # (confirmed here), so compare as naive UTC rather than assuming awareness survives.
    run_at = record.run_at if record.run_at.tzinfo else record.run_at.replace(tzinfo=timezone.utc)
    assert run_at > datetime.now(timezone.utc) + timedelta(minutes=30)


def test_expired_lease_is_reaped_and_becomes_claimable_again(tmp_path):
    engine = make_engine(tmp_path)
    task = engine.enqueue("crash_prone", {}, max_attempts=3)
    engine.claim_next("worker-1", lease_seconds=-1)  # already expired

    reaped = engine.reap_expired_leases()
    assert reaped == 1
    assert engine.get(task.id).status == "QUEUED"

    claimed = engine.claim_next("worker-2")
    assert claimed.id == task.id


def test_expired_lease_past_max_attempts_is_failed_not_requeued(tmp_path):
    engine = make_engine(tmp_path)
    task = engine.enqueue("crash_prone", {}, max_attempts=1)
    engine.claim_next("worker-1", lease_seconds=-1)

    engine.reap_expired_leases()
    assert engine.get(task.id).status == "FAILED"


def test_needs_approval_then_resume(tmp_path):
    engine = make_engine(tmp_path)
    task = engine.enqueue("send_payment", {"amount": 500})
    engine.claim_next("worker-1")

    engine.mark_needs_approval(task.id, approval_id="appr-123")
    assert engine.get(task.id).status == "NEEDS_APPROVAL"
    assert engine.claim_next("worker-2") is None  # not runnable while pending

    engine.resume_from_approval(task.id)
    assert engine.get(task.id).status == "QUEUED"
    claimed = engine.claim_next("worker-2")
    assert claimed.id == task.id


def test_cancel_removes_task_from_claimable_pool(tmp_path):
    engine = make_engine(tmp_path)
    task = engine.enqueue("send_email", {})
    engine.cancel(task.id)
    assert engine.get(task.id).status == "CANCELLED"
    assert engine.claim_next("worker-1") is None


def test_scheduled_task_is_not_claimable_before_run_at(tmp_path):
    engine = make_engine(tmp_path)
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    engine.enqueue("reminder", {}, run_at=future)
    assert engine.claim_next("worker-1") is None


def test_operating_on_unknown_task_raises(tmp_path):
    engine = make_engine(tmp_path)
    with pytest.raises(TaskNotFound):
        engine.complete("does-not-exist", {})
