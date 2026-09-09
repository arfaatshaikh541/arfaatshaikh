"""Backend Elevation: the additional authentication boundary Backend
Mode requires beyond ordinary owner/device-session authentication.

This is the real security boundary the voice-first interface redesign
depends on. Two separate, independent things are being proven here, on
purpose:

  1. Device trust (EnrollmentEngine.verify_token) -- "this request comes
     from a machine the owner has already trusted." This is what lets
     ordinary voice interaction and every other normal request skip
     re-authentication for the life of a trusted session.
  2. Backend elevation (this module) -- "the person requesting Backend
     Mode right now can prove they are the owner, again, deliberately."
     A trusted device is not enough on its own to open Backend Mode:
     the whole reason Backend Mode has its own boundary is that a
     device staying unlocked and voice-authenticated all day must not
     silently double as standing backend access.

Elevation sessions are held ONLY in this service's own process memory --
never written to the database, never serialized to disk. That is what
makes "never persist elevated backend authorization across a restart,
crash, reboot, update, or security-policy change" true structurally,
not just a rule someone has to remember to enforce elsewhere: there is
no on-disk representation of an elevated session to fail to clear.

Every authentication attempt, successful or not, is written to the real
hash-chained Audit Log. The PIN itself, its hash, and even whether a
failed attempt was "close," are never recorded or otherwise revealed --
only that an attempt happened, for which owner, and whether it was
allowed or denied.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..governance.audit_log import AuditLog
from .enrollment import EnrollmentEngine


class InvalidBackendCredentialError(RuntimeError):
    pass


class BackendRateLimitedError(RuntimeError):
    def __init__(self, retry_after_seconds: float) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"too many failed backend authentication attempts; retry after {retry_after_seconds:.0f}s")


@dataclass
class ElevationSession:
    token: str
    owner_id: str
    device_id: str
    issued_at: datetime
    expires_at: datetime

    def is_expired(self, now: datetime | None = None) -> bool:
        return (now or datetime.now(timezone.utc)) >= self.expires_at

    def seconds_remaining(self, now: datetime | None = None) -> float:
        return max(0.0, (self.expires_at - (now or datetime.now(timezone.utc))).total_seconds())


class BackendElevationService:
    def __init__(
        self, enrollment: EnrollmentEngine, audit: AuditLog, *,
        session_ttl_seconds: int = 900,
        failures_before_backoff: int = 3,
        base_backoff_seconds: float = 2.0,
        max_backoff_seconds: float = 300.0,
    ) -> None:
        self._enrollment = enrollment
        self._audit = audit
        self._ttl = timedelta(seconds=session_ttl_seconds)
        self._failures_before_backoff = failures_before_backoff
        self._base_backoff = base_backoff_seconds
        self._max_backoff = max_backoff_seconds
        self._sessions: dict[str, ElevationSession] = {}
        self._failure_counts: dict[str, int] = {}
        self._locked_until: dict[str, datetime] = {}

    def _cooldown_remaining(self, owner_id: str, now: datetime) -> float:
        locked_until = self._locked_until.get(owner_id)
        if locked_until is None or now >= locked_until:
            return 0.0
        return (locked_until - now).total_seconds()

    def _register_failure(self, owner_id: str, now: datetime) -> None:
        count = self._failure_counts.get(owner_id, 0) + 1
        self._failure_counts[owner_id] = count
        if count >= self._failures_before_backoff:
            backoff = min(self._base_backoff * (2 ** (count - self._failures_before_backoff)), self._max_backoff)
            self._locked_until[owner_id] = now + timedelta(seconds=backoff)

    def _clear_failures(self, owner_id: str) -> None:
        self._failure_counts.pop(owner_id, None)
        self._locked_until.pop(owner_id, None)

    def authenticate(self, device_token: str, pin: str) -> str:
        """Returns a fresh elevation token on success. Raises
        InvalidBackendCredentialError (device token or PIN wrong -- the
        exception never says which, so a caller learns nothing about
        which factor failed) or BackendRateLimitedError (too many recent
        failures for this owner)."""
        now = datetime.now(timezone.utc)

        device = self._enrollment.verify_token(device_token)
        if device is None:
            self._audit_attempt(actor="unknown", decision="DENY", message="invalid device token presented for backend elevation")
            raise InvalidBackendCredentialError("backend authentication failed")

        owner_id = device.owner_id
        remaining = self._cooldown_remaining(owner_id, now)
        if remaining > 0:
            self._audit_attempt(actor=owner_id, decision="DENY", message=f"rate-limited, {remaining:.0f}s remaining")
            raise BackendRateLimitedError(remaining)

        if not self._enrollment.verify_owner_pin(pin):
            self._register_failure(owner_id, now)
            self._audit_attempt(actor=owner_id, decision="DENY", message="incorrect backend credential")
            raise InvalidBackendCredentialError("backend authentication failed")

        self._clear_failures(owner_id)
        token = secrets.token_urlsafe(32)
        self._sessions[token] = ElevationSession(
            token=token, owner_id=owner_id, device_id=device.id, issued_at=now, expires_at=now + self._ttl,
        )
        self._audit_attempt(actor=owner_id, decision="ALLOW", message="backend elevation granted")
        return token

    def verify(self, elevation_token: str | None) -> ElevationSession | None:
        if elevation_token is None:
            return None
        session = self._sessions.get(elevation_token)
        if session is None:
            return None
        if session.is_expired():
            del self._sessions[elevation_token]
            return None
        return session

    def revoke(self, elevation_token: str) -> None:
        """The hotkey's Backend -> Voice transition calls this
        unconditionally -- leaving Backend Mode always destroys the
        elevation, per the product brief's explicit rule that returning
        to Voice Mode never requires authentication but always revokes
        the elevated context."""
        session = self._sessions.pop(elevation_token, None)
        if session is not None:
            self._audit_attempt(actor=session.owner_id, decision="ALLOW", message="backend elevation revoked")

    def revoke_all(self) -> None:
        """Every elevated session, for every device -- used for an
        owner-initiated "sign out of backend everywhere" action and by
        callers that need an unconditional reset (tests, security
        incident response)."""
        self._sessions.clear()

    def active_session_count(self) -> int:
        return len(self._sessions)

    def _audit_attempt(self, *, actor: str, decision: str, message: str) -> None:
        self._audit.record(
            actor=actor, action_type="security.backend_elevation_attempt", params_json="{}",
            risk_tier="RED", decision=decision,
            approval_id=None, result_status="EXECUTED" if decision == "ALLOW" else "DENIED",
            result_message=message,
        )
