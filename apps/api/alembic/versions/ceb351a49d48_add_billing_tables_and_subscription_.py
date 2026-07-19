"""add billing tables and subscription plan stripe price id

Revision ID: ceb351a49d48
Revises: eda5a5ae04d5
Create Date: 2026-07-19 06:59:17.407647

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "ceb351a49d48"
down_revision: str | Sequence[str] | None = "eda5a5ae04d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "billing_customers",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_billing_customers_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_customers")),
        sa.UniqueConstraint(
            "stripe_customer_id", name=op.f("uq_billing_customers_stripe_customer_id")
        ),
    )
    op.create_index(
        op.f("ix_billing_customers_tenant_id"), "billing_customers", ["tenant_id"], unique=True
    )

    op.create_table(
        "billing_events",
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("stripe_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_billing_events_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_events")),
        sa.UniqueConstraint("stripe_event_id", name=op.f("uq_billing_events_stripe_event_id")),
    )
    op.create_index(
        op.f("ix_billing_events_event_type"), "billing_events", ["event_type"], unique=False
    )
    op.create_index(
        op.f("ix_billing_events_tenant_id"), "billing_events", ["tenant_id"], unique=False
    )

    op.create_table(
        "billing_subscriptions",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=False),
        sa.Column("stripe_price_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_billing_subscriptions_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_subscriptions")),
        sa.UniqueConstraint(
            "stripe_subscription_id", name=op.f("uq_billing_subscriptions_stripe_subscription_id")
        ),
    )
    op.create_index(
        op.f("ix_billing_subscriptions_status"), "billing_subscriptions", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_billing_subscriptions_stripe_customer_id"),
        "billing_subscriptions",
        ["stripe_customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_subscriptions_tenant_id"),
        "billing_subscriptions",
        ["tenant_id"],
        unique=True,
    )

    op.create_table(
        "invoice_records",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("stripe_invoice_id", sa.String(length=255), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("amount_due", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("hosted_invoice_url", sa.String(length=1000), nullable=True),
        sa.Column("invoice_pdf_url", sa.String(length=1000), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_invoice_records_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoice_records")),
        sa.UniqueConstraint(
            "stripe_invoice_id", name=op.f("uq_invoice_records_stripe_invoice_id")
        ),
    )
    op.create_index(
        op.f("ix_invoice_records_status"), "invoice_records", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_invoice_records_tenant_id"), "invoice_records", ["tenant_id"], unique=False
    )

    op.add_column(
        "subscription_plans", sa.Column("stripe_price_id", sa.String(length=200), nullable=True)
    )

    # Row Level Security, same pattern as every prior milestone's migration.
    # billing_events.tenant_id is nullable (an event for a Stripe object
    # never linked to a tenant) - the policy's `tenant_id = ...` comparison
    # is simply never true for a NULL tenant_id row, so such a row is
    # invisible to every tenant and only readable under platform_bypass,
    # which is the correct behavior (see app.modules.billing.models).
    using_clause = (
        "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid "
        "OR current_setting('app.platform_bypass', true) = 'true'"
    )
    for table in ["billing_customers", "billing_subscriptions", "billing_events", "invoice_records"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({using_clause}) WITH CHECK ({using_clause})"
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table in ["invoice_records", "billing_events", "billing_subscriptions", "billing_customers"]:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_column("subscription_plans", "stripe_price_id")

    op.drop_index(op.f("ix_invoice_records_tenant_id"), table_name="invoice_records")
    op.drop_index(op.f("ix_invoice_records_status"), table_name="invoice_records")
    op.drop_table("invoice_records")

    op.drop_index(op.f("ix_billing_subscriptions_tenant_id"), table_name="billing_subscriptions")
    op.drop_index(
        op.f("ix_billing_subscriptions_stripe_customer_id"), table_name="billing_subscriptions"
    )
    op.drop_index(op.f("ix_billing_subscriptions_status"), table_name="billing_subscriptions")
    op.drop_table("billing_subscriptions")

    op.drop_index(op.f("ix_billing_events_tenant_id"), table_name="billing_events")
    op.drop_index(op.f("ix_billing_events_event_type"), table_name="billing_events")
    op.drop_table("billing_events")

    op.drop_index(op.f("ix_billing_customers_tenant_id"), table_name="billing_customers")
    op.drop_table("billing_customers")
