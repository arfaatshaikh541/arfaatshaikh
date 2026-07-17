"""Credit wallet service implementing the two-phase reserve -> commit/
release pattern described in the architecture.

Atomicity: `reserve_credits` locks the wallet row with SELECT ... FOR
UPDATE before checking `balance - sum(active_reservations) >= amount`,
so two concurrent reservation attempts against the same wallet serialize
on the row lock instead of racing past the balance check. CreditTransaction
rows are never updated or deleted by this service - corrections are
always new, additional rows.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import set_platform_bypass
from app.core.exceptions import ConflictError, InsufficientCreditsError, ResourceNotFoundError
from app.modules.usage import repositories as repo
from app.modules.usage.models import CreditReservation, CreditTransaction, CreditWallet


async def ensure_wallet(session: AsyncSession, tenant_id: uuid.UUID) -> CreditWallet:
    wallet = await repo.get_wallet_for_tenant(session, tenant_id)
    if wallet is None:
        wallet = await repo.create_wallet(session, tenant_id)
    return wallet


async def get_available_balance(session: AsyncSession, tenant_id: uuid.UUID) -> float:
    wallet = await repo.get_wallet_for_tenant(session, tenant_id)
    if wallet is None:
        return 0.0
    reserved = await repo.sum_active_reservations(session, wallet.id)
    return float(wallet.balance) - reserved


async def grant_credits(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    amount: float,
    type_: str,
    reference: str | None = None,
    created_by_user_id: uuid.UUID | None = None,
) -> CreditTransaction:
    if amount <= 0:
        raise ValueError("Grant amount must be positive.")
    wallet = await repo.get_wallet_for_update(session, tenant_id)
    if wallet is None:
        wallet = await repo.create_wallet(session, tenant_id)
    wallet.balance = float(wallet.balance) + amount
    return await repo.create_transaction(
        session,
        tenant_id=tenant_id,
        wallet_id=wallet.id,
        amount=amount,
        type_=type_,
        reference=reference,
        created_by_user_id=created_by_user_id,
    )


async def reserve_credits(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    amount: float,
    reference: str | None = None,
    expires_at: datetime | None = None,
) -> CreditReservation:
    if amount <= 0:
        raise ValueError("Reservation amount must be positive.")

    wallet = await repo.get_wallet_for_update(session, tenant_id)
    if wallet is None:
        raise ResourceNotFoundError("This tenant has no credit wallet.")

    active_reserved = await repo.sum_active_reservations(session, wallet.id)
    available = float(wallet.balance) - active_reserved
    if available < amount:
        raise InsufficientCreditsError(
            f"Insufficient credits: {available:.2f} available, {amount:.2f} requested."
        )

    return await repo.create_reservation(
        session,
        tenant_id=tenant_id,
        wallet_id=wallet.id,
        amount=amount,
        reference=reference,
        expires_at=expires_at,
    )


async def commit_reservation(
    session: AsyncSession,
    *,
    reservation_id: uuid.UUID,
    actual_amount: float,
    created_by_user_id: uuid.UUID | None = None,
) -> CreditTransaction:
    reservation = await repo.get_reservation(session, reservation_id)
    if reservation is None:
        raise ResourceNotFoundError("Reservation not found.")
    if reservation.status != "pending":
        raise ConflictError(f"Reservation is not pending (status={reservation.status}).")
    if actual_amount > float(reservation.amount):
        raise ConflictError("Actual usage cannot exceed the reserved amount.")

    wallet = await repo.get_wallet_for_update(session, reservation.tenant_id)
    if wallet is None:
        raise ResourceNotFoundError("Wallet not found.")

    wallet.balance = float(wallet.balance) - actual_amount
    reservation.status = "committed"

    return await repo.create_transaction(
        session,
        tenant_id=reservation.tenant_id,
        wallet_id=wallet.id,
        amount=-actual_amount,
        type_="debit_usage",
        reference=reservation.reference,
        reservation_id=reservation.id,
        created_by_user_id=created_by_user_id,
    )


async def release_reservation(
    session: AsyncSession, *, reservation_id: uuid.UUID
) -> CreditReservation:
    reservation = await repo.get_reservation(session, reservation_id)
    if reservation is None:
        raise ResourceNotFoundError("Reservation not found.")
    if reservation.status != "pending":
        raise ConflictError(f"Reservation is not pending (status={reservation.status}).")
    reservation.status = "released"
    return reservation


async def sweep_expired_reservations(session: AsyncSession) -> int:
    """Releases every pending reservation whose expires_at has passed,
    across all tenants. Run periodically by the worker's Celery beat
    schedule (see apps/worker/worker/beat_schedule.py). Requires
    `set_platform_bypass` since it is inherently cross-tenant; each
    individual release still only ever touches the one reservation row it
    already found, so no bulk cross-tenant data is exposed."""
    await set_platform_bypass(session)
    now = datetime.now(UTC)
    expired = await repo.list_expired_pending_reservations(session, now=now)
    for reservation in expired:
        reservation.status = "expired"
    return len(expired)
