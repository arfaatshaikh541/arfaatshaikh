import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.core.db import set_tenant_context
from app.core.exceptions import ConflictError, InsufficientCreditsError
from app.modules.usage import repositories as repo
from app.modules.usage import services
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.helpers import migrator_asyncpg_url

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def tenant_id():
    engine = create_async_engine(migrator_asyncpg_url())
    tid = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO tenants (id, name, slug, status, created_at, updated_at) "
                "VALUES (:id, 'Wallet Test Tenant', :slug, 'active', now(), now())"
            ),
            {"id": tid, "slug": f"wallet-test-{tid.hex[:8]}"},
        )
    yield tid
    await engine.dispose()


@pytest.fixture
async def app_session_factory():
    from app.core.config import get_settings

    engine = create_async_engine(get_settings().database_url)
    yield async_sessionmaker(bind=engine, expire_on_commit=False)
    await engine.dispose()


async def test_grant_and_reserve_and_commit_reduces_available_balance(
    app_session_factory, tenant_id
):
    async with app_session_factory() as session:
        await set_tenant_context(session, tenant_id)
        await services.grant_credits(
            session, tenant_id=tenant_id, amount=100, type_="grant_recurring"
        )
        await session.commit()

    async with app_session_factory() as session:
        await set_tenant_context(session, tenant_id)
        available = await services.get_available_balance(session, tenant_id)
        assert available == 100.0

        reservation = await services.reserve_credits(
            session, tenant_id=tenant_id, amount=40, reference="campaign:1"
        )
        await session.commit()

    async with app_session_factory() as session:
        await set_tenant_context(session, tenant_id)
        # Reserved amount is held: available balance drops even though
        # nothing has been actually spent yet.
        available_after_reserve = await services.get_available_balance(session, tenant_id)
        assert available_after_reserve == 60.0

        await services.commit_reservation(session, reservation_id=reservation.id, actual_amount=25)
        await session.commit()

    async with app_session_factory() as session:
        await set_tenant_context(session, tenant_id)
        wallet = await repo.get_wallet_for_tenant(session, tenant_id)
        # 100 granted - 25 actually committed = 75 remaining balance.
        assert float(wallet.balance) == 75.0
        available_after_commit = await services.get_available_balance(session, tenant_id)
        assert available_after_commit == 75.0


async def test_release_reservation_restores_available_balance(app_session_factory, tenant_id):
    async with app_session_factory() as session:
        await set_tenant_context(session, tenant_id)
        await services.grant_credits(
            session, tenant_id=tenant_id, amount=50, type_="grant_recurring"
        )
        reservation = await services.reserve_credits(
            session, tenant_id=tenant_id, amount=50, reference="campaign:2"
        )
        await session.commit()

    async with app_session_factory() as session:
        await set_tenant_context(session, tenant_id)
        assert await services.get_available_balance(session, tenant_id) == 0.0
        await services.release_reservation(session, reservation_id=reservation.id)
        await session.commit()

    async with app_session_factory() as session:
        await set_tenant_context(session, tenant_id)
        assert await services.get_available_balance(session, tenant_id) == 50.0


async def test_reservation_beyond_available_balance_is_rejected(app_session_factory, tenant_id):
    async with app_session_factory() as session:
        await set_tenant_context(session, tenant_id)
        await services.grant_credits(
            session, tenant_id=tenant_id, amount=10, type_="grant_recurring"
        )
        await session.commit()

    async with app_session_factory() as session:
        await set_tenant_context(session, tenant_id)
        with pytest.raises(InsufficientCreditsError):
            await services.reserve_credits(
                session, tenant_id=tenant_id, amount=11, reference="campaign:3"
            )


async def test_committing_more_than_reserved_is_rejected(app_session_factory, tenant_id):
    async with app_session_factory() as session:
        await set_tenant_context(session, tenant_id)
        await services.grant_credits(
            session, tenant_id=tenant_id, amount=30, type_="grant_recurring"
        )
        reservation = await services.reserve_credits(
            session, tenant_id=tenant_id, amount=30, reference="campaign:4"
        )
        await session.commit()

    async with app_session_factory() as session:
        await set_tenant_context(session, tenant_id)
        with pytest.raises(ConflictError):
            await services.commit_reservation(
                session, reservation_id=reservation.id, actual_amount=31
            )


async def test_credit_transactions_are_never_mutated_only_appended(app_session_factory, tenant_id):
    async with app_session_factory() as session:
        await set_tenant_context(session, tenant_id)
        await services.grant_credits(
            session, tenant_id=tenant_id, amount=20, type_="grant_recurring"
        )
        await services.grant_credits(session, tenant_id=tenant_id, amount=5, type_="grant_purchase")
        await session.commit()

    async with app_session_factory() as session:
        await set_tenant_context(session, tenant_id)
        transactions = await repo.list_transactions_for_tenant(session, tenant_id)
        assert len(transactions) == 2
        assert {t.type for t in transactions} == {"grant_recurring", "grant_purchase"}
        assert sum(float(t.amount) for t in transactions) == 25.0


async def test_sweep_expired_reservations_releases_stale_reservations_only(
    app_session_factory, tenant_id
):
    """Covers the same behavior the worker's `expire_stale_reservations`
    Celery task drives in production (see apps/worker/worker/tasks.py) -
    a reservation past its expiry is marked expired and its credits become
    available again, while a still-valid reservation is left untouched."""
    async with app_session_factory() as session:
        await set_tenant_context(session, tenant_id)
        await services.grant_credits(
            session, tenant_id=tenant_id, amount=100, type_="grant_recurring"
        )
        expired_reservation = await services.reserve_credits(
            session,
            tenant_id=tenant_id,
            amount=40,
            reference="expired-one",
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        still_valid_reservation = await services.reserve_credits(
            session,
            tenant_id=tenant_id,
            amount=20,
            reference="still-valid",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        await session.commit()

    async with app_session_factory() as session:
        swept_count = await services.sweep_expired_reservations(session)
        await session.commit()
    assert swept_count >= 1

    async with app_session_factory() as session:
        await set_tenant_context(session, tenant_id)
        expired = await repo.get_reservation(session, expired_reservation.id)
        still_valid = await repo.get_reservation(session, still_valid_reservation.id)
        assert expired.status == "expired"
        assert still_valid.status == "pending"

        # 100 granted - 20 still held by the valid reservation = 80 available
        # (the expired reservation's 40 is no longer held).
        available = await services.get_available_balance(session, tenant_id)
        assert available == 80.0
