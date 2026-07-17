"""Usage metrics and the credit ledger (wallet, transactions, reservations).

CreditTransaction rows are append-only at the application layer (the
service layer never issues UPDATE/DELETE against them - corrections are
new offsetting rows). CreditReservation implements the two-phase
reserve -> commit/release pattern described in the architecture so a
campaign's estimated cost can be held before work starts and reconciled
to actual usage afterward without ever allowing a negative balance.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPKMixin

TRANSACTION_TYPES = (
    "grant_recurring",
    "grant_purchase",
    "debit_usage",
    "debit_correction",
    "release_reservation",
)
RESERVATION_STATUSES = ("pending", "committed", "released", "expired")


class UsageMetric(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "usage_metrics"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)


class UsageRecord(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "usage_records"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("usage_metrics.id"), nullable=False
    )
    quantity: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CreditWallet(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "credit_wallets"
    __table_args__ = (UniqueConstraint("tenant_id", "id", name="uq_credit_wallets_tenant_id_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    balance: Mapped[float] = mapped_column(Numeric(14, 4), default=0, nullable=False)


class CreditTransaction(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "credit_transactions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "wallet_id"],
            ["credit_wallets.tenant_id", "credit_wallets.id"],
            name="fk_credit_transactions_tenant_wallet",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    wallet_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("credit_reservations.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class CreditReservation(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "credit_reservations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "wallet_id"],
            ["credit_wallets.tenant_id", "credit_wallets.id"],
            name="fk_credit_reservations_tenant_wallet",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    wallet_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
