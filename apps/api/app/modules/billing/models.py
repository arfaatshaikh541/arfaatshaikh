"""Billing entities backing a real Stripe integration - the
`BillingCustomer`/`BillingSubscription`/`BillingEvent`/`InvoiceRecord`
entities ADR-0006 deferred out of Milestone 1.

`TenantSubscription` (Milestone 1) remains the single row entitlements
are resolved from - nothing here replaces it. Instead, the Stripe
webhook handler (`services.handle_webhook_event`) is what now drives
`TenantSubscription.plan_id`/`status`/`current_period_*` after a real
plan change, the same way it was previously only ever set once by seed
data at tenant creation. These four tables are what make that sync
observable and auditable:

- `BillingCustomer`: the tenant <-> Stripe Customer mapping, created
  lazily on first checkout/portal use.
- `BillingSubscription`: a live mirror of Stripe's own subscription
  object (its real status vocabulary, not `TenantSubscription`'s
  normalized "active"/anything-else) - one row per tenant, mutated in
  place as Stripe reports changes, mirroring `TenantSubscription`'s own
  one-row-per-tenant shape.
- `BillingEvent`: every webhook event received, keyed by Stripe's own
  event id for idempotency (a redelivered event is a no-op, not a
  double-processed one) and kept regardless of whether it triggered any
  side effect - the actual audit trail for every billing state change.
  `tenant_id` is nullable: an event for a Stripe object this platform
  never linked to a tenant (e.g. one created directly in the Stripe
  dashboard) is still recorded, but - like every RLS-protected table in
  this codebase - is then only visible under the platform-bypass GUC,
  never to any tenant, which is the correct behavior for something that
  isn't actually that tenant's data.
- `InvoiceRecord`: one row per Stripe invoice, append-only.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPKMixin

INVOICE_STATUSES = ("draft", "open", "paid", "uncollectible", "void")


class BillingCustomer(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "billing_customers"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    stripe_customer_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)


class BillingSubscription(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "billing_subscriptions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    stripe_subscription_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    stripe_customer_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    stripe_price_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # Stripe's own status vocabulary, verbatim - incomplete /
    # incomplete_expired / trialing / active / past_due / canceled /
    # unpaid / paused. Deliberately not normalized to
    # `TenantSubscription.status`'s "active"/anything-else vocabulary,
    # so the real Stripe state is never lost to that simplification.
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class BillingEvent(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "billing_events"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    stripe_event_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class InvoiceRecord(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "invoice_records"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stripe_invoice_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    amount_due: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    amount_paid: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    hosted_invoice_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    invoice_pdf_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
