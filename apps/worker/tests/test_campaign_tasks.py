"""Tests for the actual page-fan-out task chain (`worker.campaign_tasks`).

These call `_run_campaign_task_async` directly rather than going through a
live Celery broker/consumer round-trip - the same approach the manual E2E
scripts used to find and fix the real bugs this suite guards against (an
asyncpg/redis-py event-loop reuse bug across `asyncio.run()` calls, and a
stale-aggregate-read bug from `AsyncSessionLocal`'s `autoflush=False`) - but
checked in so they run in CI on every change instead of only being caught by
hand.

`run_campaign_task.delay(...)` calls inside the chain do publish a Celery
message to the test broker, but nothing in this process consumes it; each
test drives the chain forward itself by fetching the next pending task and
awaiting `_run_campaign_task_async` on it directly, which is exactly what a
live worker consuming that message would do.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.modules.campaign_jobs import repositories as jobs_repo
from app.modules.campaigns import services as campaign_services
from app.modules.campaigns import state_machine
from app.modules.campaigns.schemas import CreateCampaignRequest
from app.modules.subscriptions import repositories as sub_repo
from app.modules.tenancy import repositories as tenancy_repo
from app.modules.usage import repositories as usage_repo
from app.modules.usage.services import get_available_balance, grant_credits
from sqlalchemy.ext.asyncio import async_sessionmaker
from worker.campaign_tasks import _run_campaign_task_async

pytestmark = pytest.mark.asyncio


async def _setup_and_launch_campaign(session, *, result_limit: int):
    tenant = await tenancy_repo.create_tenant(
        session, name="Worker Test Co", slug=f"wt-{uuid.uuid4().hex[:10]}"
    )
    # A tenant only gets max_concurrent_campaigns (and every other plan
    # entitlement) once it has a subscription row - real onboarding
    # (`create_tenant_for_user`) assigns the trial plan automatically, but
    # these tests create the tenant directly via the repository, so that
    # has to be done here too.
    trial_plan = await sub_repo.get_plan_by_key(session, "trial")
    assert trial_plan is not None, "seed_subscription_plans must have seeded the trial plan"
    now = datetime.now(UTC)
    await sub_repo.create_tenant_subscription(
        session,
        tenant_id=tenant.id,
        plan_id=trial_plan.id,
        current_period_start=now,
        current_period_end=now + timedelta(days=14),
    )
    await grant_credits(
        session, tenant_id=tenant.id, amount=1000.0, type_="grant_recurring", reference="test:grant"
    )
    await session.commit()

    payload = CreateCampaignRequest(
        name="Worker Test Campaign",
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
    campaign, job, task = await campaign_services.launch_campaign(session, campaign_id=campaign.id)
    await session.commit()
    return tenant, campaign, job, task


async def _drive_chain_to_completion(
    session_factory, job_id: uuid.UUID, *, max_iterations: int = 20
):
    """Repeatedly finds the next pending task for `job_id` and runs it
    directly, simulating a live worker draining the queue one page at a
    time, until no pending task remains or `max_iterations` is exhausted."""
    for _ in range(max_iterations):
        async with session_factory() as session:
            tasks = await jobs_repo.list_tasks_for_job(session, job_id)
            pending = [t for t in tasks if t.status == "pending"]
        if not pending:
            return
        await _run_campaign_task_async(str(pending[0].id))
    raise AssertionError("Task chain did not drain within max_iterations")


async def test_full_campaign_completes_via_task_chain(migrator_session):
    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)
    tenant, campaign, job, _first_task = await _setup_and_launch_campaign(
        migrator_session, result_limit=45
    )

    await _drive_chain_to_completion(session_factory, job.id)

    async with session_factory() as session:
        final_campaign = await state_machine.get_campaign_or_raise(session, campaign.id)
        assert final_campaign.status == "completed"
        total_found = await jobs_repo.sum_succeeded_businesses_for_job(session, job.id)
        assert total_found == 45
        counts = await jobs_repo.task_status_counts_for_job(session, job.id)
        assert counts == {"succeeded": 3}

        available = await get_available_balance(session, tenant.id)
        # 1000 granted - 45 actually consumed, reservation fully reconciled.
        assert available == 1000.0 - 45.0


async def test_duplicate_task_delivery_is_idempotent(migrator_session):
    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)
    _tenant, _campaign, job, first_task = await _setup_and_launch_campaign(
        migrator_session, result_limit=45
    )

    await _run_campaign_task_async(str(first_task.id))
    async with session_factory() as session:
        counts_after_first = await jobs_repo.task_status_counts_for_job(session, job.id)
    assert counts_after_first["succeeded"] == 1

    # A second, duplicate Celery delivery of the exact same (already
    # succeeded) task must be a complete no-op: no double-counted
    # businesses, no new task created, no crash.
    await _run_campaign_task_async(str(first_task.id))
    async with session_factory() as session:
        counts_after_duplicate = await jobs_repo.task_status_counts_for_job(session, job.id)
        total_found = await jobs_repo.sum_succeeded_businesses_for_job(session, job.id)

    assert counts_after_duplicate == counts_after_first
    assert total_found == 20  # first page's worth, not double-counted


async def test_pause_stops_the_chain_between_pages(migrator_session):
    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)
    tenant, campaign, job, first_task = await _setup_and_launch_campaign(
        migrator_session, result_limit=45
    )

    await _run_campaign_task_async(str(first_task.id))

    # Simulate a pause request arriving between pages, exactly like
    # `pause_campaign` would via the API once the campaign is "running".
    async with session_factory() as session:
        live_campaign = await state_machine.get_campaign_or_raise(session, campaign.id)
        assert live_campaign.status == "running"
        await state_machine.transition(session, live_campaign, to_status="pausing")
        await session.commit()

    await _drive_chain_to_completion(session_factory, job.id)

    async with session_factory() as session:
        final_campaign = await state_machine.get_campaign_or_raise(session, campaign.id)
        assert final_campaign.status == "paused"
        final_job = await jobs_repo.get_job(session, job.id)
        assert final_job.status == "paused"
        # Only the one page that already ran before the pause landed
        # counts - the pending second page must never have run.
        total_found = await jobs_repo.sum_succeeded_businesses_for_job(session, job.id)
        assert total_found == 20

        available = await get_available_balance(session, tenant.id)
        # Reservation stays open (still pending) while paused - nothing
        # committed or released yet, since the campaign might resume.
        assert available == 1000.0 - 45.0


async def test_cancel_with_no_progress_releases_the_full_reservation(migrator_session):
    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)
    tenant, campaign, job, first_task = await _setup_and_launch_campaign(
        migrator_session, result_limit=45
    )

    # Cancel before the first page ever runs (queued -> cancelling is legal).
    async with session_factory() as session:
        live_campaign = await state_machine.get_campaign_or_raise(session, campaign.id)
        await state_machine.transition(session, live_campaign, to_status="cancelling")
        await session.commit()

    await _run_campaign_task_async(str(first_task.id))

    async with session_factory() as session:
        final_campaign = await state_machine.get_campaign_or_raise(session, campaign.id)
        assert final_campaign.status == "cancelled"
        final_job = await jobs_repo.get_job(session, job.id)
        assert final_job.status == "cancelled"

        available = await get_available_balance(session, tenant.id)
        # Nothing was ever found, so the whole reservation is released, not
        # partially committed.
        assert available == 1000.0

        wallet = await usage_repo.get_wallet_for_tenant(session, tenant.id)
        assert float(wallet.balance) == 1000.0


async def test_cancel_after_partial_progress_commits_only_the_actual_amount(migrator_session):
    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)
    tenant, campaign, job, first_task = await _setup_and_launch_campaign(
        migrator_session, result_limit=45
    )

    await _run_campaign_task_async(str(first_task.id))  # first page (20) succeeds

    async with session_factory() as session:
        live_campaign = await state_machine.get_campaign_or_raise(session, campaign.id)
        assert live_campaign.status == "running"
        await state_machine.transition(session, live_campaign, to_status="cancelling")
        await session.commit()

    await _drive_chain_to_completion(session_factory, job.id)

    async with session_factory() as session:
        final_campaign = await state_machine.get_campaign_or_raise(session, campaign.id)
        assert final_campaign.status == "cancelled"
        total_found = await jobs_repo.sum_succeeded_businesses_for_job(session, job.id)
        assert total_found == 20

        available = await get_available_balance(session, tenant.id)
        # Only the 20 actually found get committed; the remaining 25 of
        # the 45-credit reservation are released back, not silently kept.
        assert available == 1000.0 - 20.0

        wallet = await usage_repo.get_wallet_for_tenant(session, tenant.id)
        assert float(wallet.balance) == 1000.0 - 20.0
