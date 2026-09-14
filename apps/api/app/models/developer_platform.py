from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DeveloperApplication(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "developer_applications"
    __table_args__ = (
        CheckConstraint("status IN ('draft','active','suspended','revoked')", name="ck_developer_application_status"),
        CheckConstraint("application_type IN ('first_party','partner','public')", name="ck_developer_application_type"),
        UniqueConstraint("organisation_id", "slug", name="uq_developer_application_org_slug"),
        Index("ix_developer_application_org_status", "organisation_id", "status"),
    )

    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    application_type: Mapped[str] = mapped_column(String(20), nullable=False, default="partner", server_default="partner")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    privacy_policy_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    terms_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")


class APIClientCredential(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_client_credentials"
    __table_args__ = (
        CheckConstraint("status IN ('active','rotating','revoked','expired')", name="ck_api_client_credential_status"),
        CheckConstraint("rate_limit_per_minute > 0 AND rate_limit_per_minute <= 6000", name="ck_api_client_credential_rate_limit"),
        UniqueConstraint("key_prefix", name="uq_api_client_credential_prefix"),
        Index("ix_api_client_credential_application_status", "application_id", "status"),
    )

    application_id: Mapped[UUID] = mapped_column(ForeignKey("developer_applications.id", ondelete="CASCADE"), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=60, server_default="60")
    expires_at_iso: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_used_at_iso: Mapped[str | None] = mapped_column(String(40), nullable=True)
    rotated_from_id: Mapped[UUID | None] = mapped_column(ForeignKey("api_client_credentials.id", ondelete="SET NULL"), nullable=True)


class APIClientScope(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_client_scopes"
    __table_args__ = (
        UniqueConstraint("credential_id", "scope", name="uq_api_client_scope_credential_scope"),
        Index("ix_api_client_scope_scope", "scope"),
    )

    credential_id: Mapped[UUID] = mapped_column(ForeignKey("api_client_credentials.id", ondelete="CASCADE"), nullable=False)
    scope: Mapped[str] = mapped_column(String(80), nullable=False)
    granted_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)


class WebhookSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "webhook_subscriptions"
    __table_args__ = (
        CheckConstraint("status IN ('pending','active','paused','failed','revoked')", name="ck_webhook_subscription_status"),
        CheckConstraint("failure_count >= 0", name="ck_webhook_subscription_failure_count"),
        UniqueConstraint("application_id", "endpoint_url", name="uq_webhook_subscription_application_endpoint"),
        Index("ix_webhook_subscription_application_status", "application_id", "status"),
    )

    application_id: Mapped[UUID] = mapped_column(ForeignKey("developer_applications.id", ondelete="CASCADE"), nullable=False)
    endpoint_url: Mapped[str] = mapped_column(Text, nullable=False)
    signing_secret_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    subscribed_events: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_verified_at_iso: Mapped[str | None] = mapped_column(String(40), nullable=True)


class WebhookDelivery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        CheckConstraint("status IN ('queued','delivering','delivered','retrying','failed','discarded')", name="ck_webhook_delivery_status"),
        CheckConstraint("attempt_count >= 0 AND attempt_count <= 12", name="ck_webhook_delivery_attempt_count"),
        UniqueConstraint("subscription_id", "event_id", name="uq_webhook_delivery_subscription_event"),
        Index("ix_webhook_delivery_subscription_status", "subscription_id", "status"),
    )

    subscription_id: Mapped[UUID] = mapped_column(ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"), nullable=False)
    event_id: Mapped[str] = mapped_column(String(80), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", server_default="queued")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    response_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
