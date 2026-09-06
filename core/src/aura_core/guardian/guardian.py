"""Security Guardian: independent oversight outside the Executive/agent
hierarchy. Reads the audit log (never writes to it), can engage the kill
switch, and has no `disable()` method — deliberately absent, not merely
unimplemented. See docs/adr/0003-security-guardian-separate-trust-
boundary.md.

evaluate() looks at a rolling time window (not "everything new since last
call"): it's called after every single Action Broker write via the
on_audit hook, and a strictly-incremental watermark would mean each call
sees a batch of exactly one entry, making any threshold/velocity rule
mathematically unable to fire. A time window lets rules see the real
recent pattern regardless of how often evaluate() happens to be invoked.
To avoid re-recording the same ongoing condition on every subsequent call
while it's still within the window, a rule that already has a recorded
event inside the window is not re-fired.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from ..governance.audit_log import AuditLog
from ..governance.policy_engine import PolicyEngine
from ..memory.models import Base
from .models import GuardianEvent
from .rules import DEFAULT_RULES, GuardianRule

DEFAULT_WINDOW_SECONDS = 60


class SecurityGuardian:
    def __init__(
        self, audit_log: AuditLog, policy_engine: PolicyEngine, database_url: str,
        rules: list[GuardianRule] | None = None, window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        self._audit = audit_log
        self._policy = policy_engine
        self._rules = rules if rules is not None else DEFAULT_RULES
        self._window_seconds = window_seconds

        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(database_url, connect_args=connect_args)
        Base.metadata.create_all(self._engine)
        self._Session = sessionmaker(bind=self._engine)

    def evaluate(self) -> list[GuardianEvent]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._window_seconds)
        cutoff_iso = cutoff.isoformat()
        recent_entries = self._audit.entries_since(cutoff_iso)
        if not recent_entries:
            return []

        fired: list[GuardianEvent] = []
        with self._Session() as session:
            for rule in self._rules:
                reason = rule.check(recent_entries)
                if reason is None:
                    continue

                already_recorded_in_window = session.scalars(
                    select(GuardianEvent)
                    .where(GuardianEvent.rule_name == rule.name)
                    .where(GuardianEvent.detected_at >= cutoff)
                ).first()
                if already_recorded_in_window is not None:
                    continue  # same ongoing condition already handled this window

                already_engaged = self._policy.is_kill_switch_engaged()
                if not already_engaged:
                    self._policy.engage_kill_switch()
                action_taken = "LOGGED_ONLY" if already_engaged else "KILL_SWITCH_ENGAGED"

                event = GuardianEvent(rule_name=rule.name, detail=reason, action_taken=action_taken)
                session.add(event)
                fired.append(event)

            session.commit()
            for event in fired:
                session.refresh(event)
        return fired

    def freeze(self, reason: str) -> GuardianEvent:
        """Manual/explicit freeze, independent of the rule engine — e.g.
        triggered from a fire-drill or an external monitoring signal."""
        self._policy.engage_kill_switch()
        with self._Session() as session:
            event = GuardianEvent(rule_name="manual", detail=reason, action_taken="KILL_SWITCH_ENGAGED")
            session.add(event)
            session.commit()
            session.refresh(event)
            return event

    def recent_events(self, limit: int = 50) -> list[GuardianEvent]:
        with self._Session() as session:
            stmt = select(GuardianEvent).order_by(GuardianEvent.detected_at.desc()).limit(limit)
            return list(session.scalars(stmt))

    # No disable()/pause()/reconfigure_rules() method exists. Rule changes
    # are a code change (reviewed like any other), not a runtime API call
    # any in-process caller — including a future Executive Intelligence —
    # can reach.
