"""Drives the real Celery-wrapped `worker.campaign_tasks.run_campaign_task`
end-to-end with a controlled, deterministic sequence of connector failures
(`connector_sdk.fault_injecting.FaultInjectingConnector`) - closing the
"no connector-error-path test coverage through the worker's own retry
loop" gap named since Milestone 3.

Test functions here are deliberately plain (non-`async def`) functions,
not `pytest.mark.asyncio` coroutines: `run_campaign_task` calls the real
`worker.async_utils.run_db_task`, which wraps `asyncio.run(...)` -  illegal
nested inside pytest-asyncio's own session-scoped running loop, exactly
the collision `worker.async_utils`'s own docstring and `worker.retry`'s
tests both already had to work around. Each test instead drives its own
async setup/verification through explicit, self-contained `asyncio.run(...)`
calls - one per phase, each starting and fully closing its own loop before
the next begins, which is actually a more faithful simulation of how a
real Celery worker process behaves (a fresh loop per task) than sharing one
long-lived test-session loop would be. `reset_database`/`apply_migrations`
(conftest.py's autouse fixtures) still run normally regardless of a test
function's sync/async shape.

Every test also requests `real_celery_task_isolation` (conftest.py): the
production DB engine/redis client accumulate connections bound to
pytest-asyncio's session loop from *other* test files' ordinary direct-
async-call style tests, and the first real `run_db_task` call in the
whole test session would otherwise try to close them from this file's own,
unrelated fresh loop and hit the exact cross-loop error this module works
around one level up - see that fixture's own docstring for the full
mechanism.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from app.modules.campaign_jobs import repositories as jobs_repo
from app.modules.campaigns import services as campaign_services
from app.modules.campaigns import state_machine
from app.modules.campaigns.schemas import CreateCampaignRequest
from app.modules.subscriptions import repositories as sub_repo
from app.modules.tenancy import repositories as tenancy_repo
from app.modules.usage.services import get_available_balance, grant_credits
from celery.exceptions import Retry
from connector_sdk.errors import ConnectorAuthError, ConnectorTransientError
from connector_sdk.fault_injecting import FaultInjectingConnector
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from worker import campaign_tasks as ct


def _session_factory():
    from app.core.config import get_settings

    url = get_settings().database_url_sync.replace("postgresql+psycopg", "postgresql+asyncpg")
    engine = create_async_engine(url)
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False)


async def _setup_and_launch_campaign(*, result_limit: int):
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await tenancy_repo.create_tenant(
                session, name="Retry Loop Test Co", slug=f"rl-{uuid.uuid4().hex[:10]}"
            )
            trial_plan = await sub_repo.get_plan_by_key(session, "trial")
            assert trial_plan is not None
            now = datetime.now(UTC)
            await sub_repo.create_tenant_subscription(
                session,
                tenant_id=tenant.id,
                plan_id=trial_plan.id,
                current_period_start=now,
                current_period_end=now + timedelta(days=14),
            )
            await grant_credits(
                session,
                tenant_id=tenant.id,
                amount=1000.0,
                type_="grant_recurring",
                reference="test:grant",
            )
            await session.commit()

            payload = CreateCampaignRequest(
                name="Retry Loop Test Campaign",
                source_key="mock",
                result_limit=result_limit,
                industry="Restaurants",
                category="Restaurants",
                country="United Arab Emirates",
                city="Dubai",
                area="Dubai Marina",
                min_rating=3.5,
                min_reviews=20,
                must_have_phone=True,
                website_requirement="any",
            )
            campaign = await campaign_services.create_campaign(
                session, tenant_id=tenant.id, user_id=None, payload=payload
            )
            await session.commit()
            await campaign_services.compute_estimate(session, campaign_id=campaign.id)
            await session.commit()
            campaign, job, task = await campaign_services.launch_campaign(
                session, campaign_id=campaign.id
            )
            await session.commit()
            return tenant.id, campaign.id, job.id, task.id
    finally:
        await engine.dispose()


async def _get_task_status(task_id) -> str:
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            task = await jobs_repo.get_task(session, task_id)
            return task.status
    finally:
        await engine.dispose()


def test_transient_connector_error_retries_then_succeeds(monkeypatch, real_celery_task_isolation):
    """Proves the retry actually re-invokes the connector, not just burns
    through the retry budget doing nothing: `lock_task_for_processing`
    only reclaims a task from `pending`, so if a genuine retry (same
    task_id, same status left over from the failed attempt) can't see the
    task as `pending` again, it silently no-ops on every subsequent
    delivery instead of ever re-attempting the connector call."""
    tenant_id, campaign_id, job_id, task_id = asyncio.run(
        _setup_and_launch_campaign(result_limit=5)
    )

    connector = FaultInjectingConnector([ConnectorTransientError("simulated transient failure")])
    monkeypatch.setattr(ct, "get_connector", lambda source_key: connector)

    task = ct.run_campaign_task
    task.push_request(called_directly=False, retries=0)
    try:
        raised = False
        try:
            task(str(task_id))
        except Retry:
            raised = True
        assert raised, "expected a Retry exception on the first (transient-failure) attempt"
    finally:
        task.pop_request()

    # If this is "running" instead of "pending", the real retried
    # delivery below will no-op instead of re-attempting the call.
    assert asyncio.run(_get_task_status(task_id)) == "pending"

    # Simulates the real worker consuming the retried delivery: same
    # task_id, retries incremented by Celery's own machinery.
    task.push_request(called_directly=False, retries=1)
    try:
        task(str(task_id))
    finally:
        task.pop_request()

    assert connector.call_count == 2  # the retry genuinely re-invoked search()
    assert asyncio.run(_get_task_status(task_id)) == "succeeded"


def test_transient_connector_error_exhausting_retries_finalizes_cleanly(
    monkeypatch, real_celery_task_isolation
):
    tenant_id, campaign_id, job_id, task_id = asyncio.run(
        _setup_and_launch_campaign(result_limit=5)
    )

    connector = FaultInjectingConnector([ConnectorTransientError("always fails")] * 20)
    monkeypatch.setattr(ct, "get_connector", lambda source_key: connector)

    task = ct.run_campaign_task
    task.push_request(called_directly=False, retries=task.max_retries)
    try:
        task(str(task_id))  # must not raise - exhausted retries finalize instead
    finally:
        task.pop_request()

    async def _verify():
        engine, Session = _session_factory()
        try:
            async with Session() as session:
                refreshed_task = await jobs_repo.get_task(session, task_id)
                assert refreshed_task.status == "failed"
                assert refreshed_task.error_message is not None

                final_campaign = await state_machine.get_campaign_or_raise(session, campaign_id)
                assert final_campaign.status == "failed"

                # No businesses were ever found - the reservation must be fully released.
                available = await get_available_balance(session, tenant_id)
                assert available == 1000.0
        finally:
            await engine.dispose()

    asyncio.run(_verify())


def test_auth_connector_error_fails_immediately_without_retrying(monkeypatch, real_celery_task_isolation):
    """Auth/permanent/quota errors are caught inside `_run_campaign_task_
    async` itself and finalize immediately - never routed through
    `retry_or_finalize` at all. Driven through the real Celery-wrapped
    task for parity with the transient-error tests above, not just
    `_run_campaign_task_async` directly."""
    tenant_id, campaign_id, job_id, task_id = asyncio.run(
        _setup_and_launch_campaign(result_limit=5)
    )

    connector = FaultInjectingConnector([ConnectorAuthError("invalid api key")])
    monkeypatch.setattr(ct, "get_connector", lambda source_key: connector)

    task = ct.run_campaign_task
    task.push_request(called_directly=False, retries=0)
    try:
        task(str(task_id))  # must not raise - fails immediately, no retry
    finally:
        task.pop_request()

    assert connector.call_count == 1  # never retried
    assert asyncio.run(_get_task_status(task_id)) == "failed"
