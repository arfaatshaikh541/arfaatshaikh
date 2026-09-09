"""Governance persistence schema: Policy Engine state, Approval queue, and
Audit Log. Registered on the same declarative Base as the memory schema
(`aura_core.memory.models.Base`) so a single SQLite file holds both — see
each store's docstring for why sharing one engine-per-store pattern is
fine here rather than introducing a shared connection-pool abstraction.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..memory.models import Base, _now, _uuid


class PolicyState(Base):
    """Singleton row (id is always 1) holding the kill switch."""

    __tablename__ = "policy_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kill_switch_engaged: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ActionPolicy(Base):
    """Autonomy level (0-5) configured per action_type. Absence of a row
    means level 0 (Observe only) — fail closed, per
    docs/policies/README.md#autonomy-levels."""

    __tablename__ = "action_policies"

    action_type: Mapped[str] = mapped_column(String(150), primary_key=True)
    autonomy_level: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")


class ProhibitedAction(Base):
    __tablename__ = "prohibited_actions"

    action_type: Mapped[str] = mapped_column(String(150), primary_key=True)
    reason: Mapped[str] = mapped_column(Text, default="")


class BudgetEnvelope(Base):
    __tablename__ = "budget_envelopes"

    budget_key: Mapped[str] = mapped_column(String(150), primary_key=True)
    limit_amount: Mapped[float] = mapped_column(Float)
    spent_amount: Mapped[float] = mapped_column(Float, default=0.0)


class ApprovalRecord(Base):
    __tablename__ = "approval_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    action_type: Mapped[str] = mapped_column(String(150))
    params_json: Mapped[str] = mapped_column(Text)
    requested_by: Mapped[str] = mapped_column(String(200))
    risk_tier: Mapped[str] = mapped_column(String(10))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|denied
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(200), nullable=True)


class AuditEntry(Base):
    """Hash-chained, append-only. `seq` is the autoincrement ordering key;
    `timestamp_iso` is stored verbatim and reused during verification so
    the hash never depends on a DateTime column round-tripping through the
    database driver identically to how it was formatted at write time."""

    __tablename__ = "audit_entries"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(36), default=_uuid)
    timestamp_iso: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(200))
    action_type: Mapped[str] = mapped_column(String(150))
    params_json: Mapped[str] = mapped_column(Text)
    risk_tier: Mapped[str] = mapped_column(String(10))
    decision: Mapped[str] = mapped_column(String(30))
    approval_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    result_status: Mapped[str] = mapped_column(String(30))
    result_message: Mapped[str] = mapped_column(Text, default="")
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
