from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.dependencies import TenantContext, require_permission
from app.modules.usage import repositories as repo
from app.modules.usage import services
from app.modules.usage.schemas import CreditTransactionResponse, WalletBalanceResponse

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/wallet", response_model=WalletBalanceResponse)
async def get_wallet_balance(
    ctx: TenantContext = Depends(require_permission("usage.view")),
    db: AsyncSession = Depends(get_db),
):
    wallet = await services.ensure_wallet(db, ctx.tenant_id)
    available = await services.get_available_balance(db, ctx.tenant_id)
    return WalletBalanceResponse(
        tenant_id=ctx.tenant_id, balance=float(wallet.balance), available=available
    )


@router.get("/transactions", response_model=list[CreditTransactionResponse])
async def list_transactions(
    ctx: TenantContext = Depends(require_permission("usage.view")),
    db: AsyncSession = Depends(get_db),
):
    transactions = await repo.list_transactions_for_tenant(db, ctx.tenant_id)
    return [
        CreditTransactionResponse(
            id=t.id,
            amount=float(t.amount),
            type=t.type,
            reference=t.reference,
            created_at=t.created_at,
        )
        for t in transactions
    ]
