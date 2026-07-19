import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.models import (
    BillingCustomer,
    BillingEvent,
    BillingSubscription,
    InvoiceRecord,
)


async def get_billing_customer_for_tenant(
    session: AsyncSession, tenant_id: uuid.UUID
) -> BillingCustomer | None:
    stmt = select(BillingCustomer).where(BillingCustomer.tenant_id == tenant_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_billing_customer_by_stripe_id(
    session: AsyncSession, stripe_customer_id: str
) -> BillingCustomer | None:
    stmt = select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_billing_customer(
    session: AsyncSession, *, tenant_id: uuid.UUID, stripe_customer_id: str
) -> BillingCustomer:
    customer = BillingCustomer(tenant_id=tenant_id, stripe_customer_id=stripe_customer_id)
    session.add(customer)
    await session.flush()
    return customer


async def get_billing_subscription_for_tenant(
    session: AsyncSession, tenant_id: uuid.UUID
) -> BillingSubscription | None:
    stmt = select(BillingSubscription).where(BillingSubscription.tenant_id == tenant_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def upsert_billing_subscription(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    stripe_subscription_id: str,
    stripe_customer_id: str,
    stripe_price_id: str,
    status: str,
    current_period_start: datetime,
    current_period_end: datetime,
    cancel_at_period_end: bool,
) -> BillingSubscription:
    existing = await get_billing_subscription_for_tenant(session, tenant_id)
    if existing is not None:
        existing.stripe_subscription_id = stripe_subscription_id
        existing.stripe_customer_id = stripe_customer_id
        existing.stripe_price_id = stripe_price_id
        existing.status = status
        existing.current_period_start = current_period_start
        existing.current_period_end = current_period_end
        existing.cancel_at_period_end = cancel_at_period_end
        await session.flush()
        return existing
    subscription = BillingSubscription(
        tenant_id=tenant_id,
        stripe_subscription_id=stripe_subscription_id,
        stripe_customer_id=stripe_customer_id,
        stripe_price_id=stripe_price_id,
        status=status,
        current_period_start=current_period_start,
        current_period_end=current_period_end,
        cancel_at_period_end=cancel_at_period_end,
    )
    session.add(subscription)
    await session.flush()
    return subscription


async def get_billing_event_by_stripe_id(
    session: AsyncSession, stripe_event_id: str
) -> BillingEvent | None:
    stmt = select(BillingEvent).where(BillingEvent.stripe_event_id == stripe_event_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_billing_event(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID | None,
    stripe_event_id: str,
    event_type: str,
    processed_at: datetime,
    payload: dict,
) -> BillingEvent:
    event = BillingEvent(
        tenant_id=tenant_id,
        stripe_event_id=stripe_event_id,
        event_type=event_type,
        processed_at=processed_at,
        payload=payload,
    )
    session.add(event)
    await session.flush()
    return event


async def get_invoice_by_stripe_id(
    session: AsyncSession, stripe_invoice_id: str
) -> InvoiceRecord | None:
    stmt = select(InvoiceRecord).where(InvoiceRecord.stripe_invoice_id == stripe_invoice_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_invoice_by_stripe_id_for_update(
    session: AsyncSession, stripe_invoice_id: str
) -> InvoiceRecord | None:
    """Locks the row (SELECT ... FOR UPDATE) so two concurrent webhook
    deliveries for the same invoice serialize on this row instead of both
    reading `credit_grant_applied_at` as unset and double-granting - see
    `billing.services._grant_recurring_credits_for_invoice`."""
    stmt = (
        select(InvoiceRecord)
        .where(InvoiceRecord.stripe_invoice_id == stripe_invoice_id)
        .with_for_update()
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def upsert_invoice_record(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    stripe_invoice_id: str,
    stripe_subscription_id: str | None,
    status: str,
    amount_due: float,
    amount_paid: float,
    currency: str,
    hosted_invoice_url: str | None,
    invoice_pdf_url: str | None,
    period_start: datetime | None,
    period_end: datetime | None,
    paid_at: datetime | None,
) -> InvoiceRecord:
    existing = await get_invoice_by_stripe_id(session, stripe_invoice_id)
    if existing is not None:
        existing.status = status
        existing.amount_due = amount_due
        existing.amount_paid = amount_paid
        existing.currency = currency
        existing.hosted_invoice_url = hosted_invoice_url
        existing.invoice_pdf_url = invoice_pdf_url
        existing.period_start = period_start
        existing.period_end = period_end
        existing.paid_at = paid_at
        await session.flush()
        return existing
    invoice = InvoiceRecord(
        tenant_id=tenant_id,
        stripe_invoice_id=stripe_invoice_id,
        stripe_subscription_id=stripe_subscription_id,
        status=status,
        amount_due=amount_due,
        amount_paid=amount_paid,
        currency=currency,
        hosted_invoice_url=hosted_invoice_url,
        invoice_pdf_url=invoice_pdf_url,
        period_start=period_start,
        period_end=period_end,
        paid_at=paid_at,
    )
    session.add(invoice)
    await session.flush()
    return invoice


async def list_invoices_for_tenant(
    session: AsyncSession, tenant_id: uuid.UUID, *, limit: int = 50
) -> list[InvoiceRecord]:
    stmt = (
        select(InvoiceRecord)
        .where(InvoiceRecord.tenant_id == tenant_id)
        .order_by(InvoiceRecord.created_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())
