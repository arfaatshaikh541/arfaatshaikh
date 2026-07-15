from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from modules.assets.models import Asset

# Matches packages/security-contracts AUTOMATION_MODES exactly (kept in
# sync manually here the same way modules elsewhere mirror shared-vocab
# string literals — see core/security_contracts.py for the canonical
# cross-language copy this module doesn't duplicate again).
AUTOMATION_MODES = ("observe", "guided", "balanced", "autopilot", "lockdown")
ACTION_RUN_STATUSES = ("pending_approval", "approved", "rejected", "running", "succeeded", "failed")
ACTION_TRIGGERS = ("manual", "playbook")


class TenantAutomationSetting(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """One row per tenant. Absence of a row means `observe` — the safest
    default (see modules.actions.policy) — so a brand-new tenant never
    has automation silently enabled by omission."""

    __tablename__ = "tenant_automation_settings"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_tenant_automation_settings_tenant"),)

    mode: Mapped[str] = mapped_column(
        Enum(*AUTOMATION_MODES, name="automation_mode"), nullable=False, default="observe"
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class Playbook(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Maps a finding's `rule_key` to an `action_key` to take when that
    rule fires. `action_key` is resolved against whichever connector
    actually services the matching finding's asset at evaluation time
    (modules.actions.service.evaluate_playbooks_for_findings) — not
    validated against a specific provider here, since the same rule_key
    can appear on assets from different providers over a tenant's
    lifetime."""

    __tablename__ = "playbooks"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rule_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    action_key: Mapped[str] = mapped_column(String(80), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ActionRun(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """One attempt to execute a connector action against one asset —
    manually requested by a human or created by playbook evaluation after
    correlation. `safety_class` and `provider_id` are captured at request
    time (not re-derived from the connector at read time) so a run's
    record stays accurate even if the connector's definition changes
    later."""

    __tablename__ = "action_runs"

    action_key: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(80), nullable=False)
    safety_class: Mapped[int] = mapped_column(Integer, nullable=False)
    tenant_integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant_integrations.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("findings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    playbook_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("playbooks.id", ondelete="SET NULL"), nullable=True
    )
    trigger: Mapped[str] = mapped_column(Enum(*ACTION_TRIGGERS, name="action_trigger"), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(*ACTION_RUN_STATUSES, name="action_run_status"),
        nullable=False,
        default="pending_approval",
        index=True,
    )
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    result_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    asset: Mapped[Asset] = relationship()
