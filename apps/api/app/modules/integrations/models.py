"""Integration and IntegrationDelivery.

Milestone 1's permission catalog reserved `integrations.view`/
`integrations.manage` years before this milestone needed them - the same
"reserved ahead of time, unused until now" pattern `leads.export` and the
S3 object-storage config had before Milestone 7. Milestone 8 is "CRM
delivery" (see `worker.queues.QUEUE_CRM_PUSH`'s own comment, declared
since Milestone 2).

An `Integration` here is deliberately a generic outbound **webhook**, not
a named third-party CRM (HubSpot, Salesforce, Pipedrive, ...). Building a
connector against a real CRM's API would need real credentials this
project has never had access to - the same reasoning ADR-0010 (Google
Places) and ADR-0012 (the SSRF crawler) already applied: don't build
something that can only be verified by documentation-reasoning, when a
webhook is a shape every real CRM/automation platform (Zapier, Make,
n8n, or a CRM's own "custom webhook" trigger) already knows how to
receive, and - unlike a fabricated named-CRM adapter - is fully,
genuinely testable end-to-end against a real HTTP receiver. See
docs/adr/0016.

`Integration.webhook_secret_encrypted` is real, reversible encryption
(`app.core.security.encrypt_credential`), not a hash - the secret must be
recovered in full to HMAC-sign each outgoing delivery. It is never
returned to the client in plaintext after creation; see
`schemas.IntegrationResponse`.

`IntegrationDelivery` is the append-only audit trail of every push
attempt - same "the entity's own history table is the audit record"
pattern `LeadStatusHistory`/`CampaignEvent`/`Export` already established,
not a re-use of the generic `AuditLog` (which, as of Milestone 7, is
still used exclusively by `tenancy`/`platform_admin`).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPKMixin

INTEGRATION_TYPES = ("webhook",)
DELIVERY_STATUSES = ("pending", "success", "failed")


class Integration(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "integrations"
    __table_args__ = (UniqueConstraint("tenant_id", "id", name="uq_integrations_tenant_id_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(30), default="webhook", nullable=False)
    webhook_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    webhook_secret_encrypted: Mapped[str] = mapped_column(String(1000), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class IntegrationDelivery(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "integration_deliveries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "integration_id"],
            ["integrations.tenant_id", "integrations.id"],
            name="fk_integration_deliveries_tenant_integration",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    integration_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # A truncated snippet of the receiver's response body - enough to
    # diagnose a failure, never the full arbitrary response of a
    # third-party endpoint retained indefinitely.
    response_snippet: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
