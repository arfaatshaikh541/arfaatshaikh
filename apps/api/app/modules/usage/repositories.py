import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.usage.models import CreditReservation, CreditTransaction, CreditWallet


async def get_wallet_for_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> CreditWallet | None:
    stmt = select(CreditWallet).where(CreditWallet.tenant_id == tenant_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_wallet_for_update(session: AsyncSession, tenant_id: uuid.UUID) -> CreditWallet | None:
    """Locks the wallet row (SELECT ... FOR UPDATE) so concurrent reservation
    attempts serialize instead of racing on the balance check."""
    stmt = select(CreditWallet).where(CreditWallet.tenant_id == tenant_id).with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_wallet(session: AsyncSession, tenant_id: uuid.UUID) -> CreditWallet:
    wallet = CreditWallet(tenant_id=tenant_id, balance=0)
    session.add(wallet)
    await session.flush()
    return wallet


async def sum_active_reservations(session: AsyncSession, wallet_id: uuid.UUID) -> float:
    stmt = select(CreditReservation).where(
        CreditReservation.wallet_id == wallet_id, CreditReservation.status == "pending"
    )
    rows = (await session.execute(stmt)).scalars().all()
    return float(sum(r.amount for r in rows))


async def create_reservation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    wallet_id: uuid.UUID,
    amount: float,
    reference: str | None,
    expires_at: datetime | None,
) -> CreditReservation:
    reservation = CreditReservation(
        tenant_id=tenant_id,
        wallet_id=wallet_id,
        amount=amount,
        reference=reference,
        expires_at=expires_at,
    )
    session.add(reservation)
    await session.flush()
    return reservation


async def get_reservation(
    session: AsyncSession, reservation_id: uuid.UUID
) -> CreditReservation | None:
    stmt = select(CreditReservation).where(CreditReservation.id == reservation_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_transaction(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    wallet_id: uuid.UUID,
    amount: float,
    type_: str,
    reference: str | None = None,
    reservation_id: uuid.UUID | None = None,
    created_by_user_id: uuid.UUID | None = None,
) -> CreditTransaction:
    txn = CreditTransaction(
        tenant_id=tenant_id,
        wallet_id=wallet_id,
        amount=amount,
        type=type_,
        reference=reference,
        reservation_id=reservation_id,
        created_by_user_id=created_by_user_id,
    )
    session.add(txn)
    await session.flush()
    return txn


async def list_transactions_for_tenant(
    session: AsyncSession, tenant_id: uuid.UUID
) -> list[CreditTransaction]:
    stmt = (
        select(CreditTransaction)
        .where(CreditTransaction.tenant_id == tenant_id)
        .order_by(CreditTransaction.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_expired_pending_reservations(
    session: AsyncSession, *, now: datetime
) -> list[CreditReservation]:
    """Cross-tenant query used only by the maintenance sweep task, which
    runs under `set_platform_bypass` - there is no single tenant to scope
    this to, since the whole point is finding stale reservations across
    every tenant."""
    stmt = select(CreditReservation).where(
        CreditReservation.status == "pending",
        CreditReservation.expires_at.is_not(None),
        CreditReservation.expires_at < now,
    )
    return list((await session.execute(stmt)).scalars().all())
