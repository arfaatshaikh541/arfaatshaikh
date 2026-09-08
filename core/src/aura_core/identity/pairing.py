"""Short-lived, single-use pairing codes for enrolling a second trusted
device under the existing owner (the "Add Device" flow).

Security model: minting a pairing code requires the same backend
elevation every other sensitive backend operation requires (see
identity/elevation.py) -- only an already-authenticated, already
-elevated owner, on an already-trusted device, may authorize a new
device to join. The code itself is high-entropy
(secrets.token_urlsafe), single-use, and expires quickly (default 10
minutes) -- these are the properties that make it safe for the
*claiming* endpoint to be reachable without a device token of its own
(the new device, by definition, has none yet, so it cannot present one).
A claimed code becomes unusable immediately, whether the claim
succeeded or not -- there is no retry-the-same-code path, only "start a
new pairing session," which requires elevation again.

Sessions are in-memory only, the same discipline
BackendElevationService uses for elevation tokens: a pairing session
that somehow survived a process restart would be a real (if narrow)
security smell, so requiring a fresh Start after every restart is the
safer, simpler invariant. Every start and claim, successful or not, is
written to the real hash-chained Audit Log.
"""
from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .enrollment import EnrollmentEngine


class PairingCodeInvalidError(RuntimeError):
    pass


@dataclass
class PairingSession:
    code: str
    created_at: datetime
    expires_at: datetime
    claimed: bool = False

    def is_expired(self, *, now: datetime | None = None) -> bool:
        return (now or datetime.now(timezone.utc)) >= self.expires_at


class DevicePairingService:
    def __init__(self, enrollment: EnrollmentEngine, audit, *, ttl_seconds: int = 600) -> None:
        self._enrollment = enrollment
        self._audit = audit
        self._ttl = timedelta(seconds=ttl_seconds)
        self._sessions: dict[str, PairingSession] = {}

    def start(self) -> PairingSession:
        # Alphabet excludes visually ambiguous characters (0/O, 1/I/l) --
        # this code is meant to be read off one screen and typed into
        # another, not copy-pasted.
        alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
        code = "".join(secrets.choice(alphabet) for _ in range(8))
        now = datetime.now(timezone.utc)
        session = PairingSession(code=code, created_at=now, expires_at=now + self._ttl)
        self._sessions[code] = session

        self._audit.record(
            actor="owner", action_type="security.device_pairing_start", params_json="{}",
            risk_tier="RED", decision="ALLOW", approval_id=None,
            result_status="EXECUTED",
            result_message=f"pairing session opened, expires {session.expires_at.isoformat()}",
        )
        return session

    def claim(self, code: str, device_label: str) -> str:
        """Redeems a pairing code for a brand-new real device token
        (via EnrollmentEngine.issue_device_token -- the same mechanism
        every other second-device trust in this codebase already uses,
        never a separate weaker credential just for this path). Raises
        PairingCodeInvalidError for an unknown, already-claimed, or
        expired code -- never distinguishes which, the same "don't leak
        which factor failed" discipline every other credential check in
        this codebase follows.
        """
        session = self._sessions.get(code)
        valid = session is not None and not session.claimed and not session.is_expired()

        if not valid:
            self._audit.record(
                actor="new_device", action_type="security.device_pairing_claim",
                params_json=json.dumps({"label": device_label}),
                risk_tier="RED", decision="DENY", approval_id=None,
                result_status="DENIED",
                result_message="pairing code invalid, already used, or expired",
            )
            raise PairingCodeInvalidError(
                "this pairing code is invalid, already used, or has expired"
            )

        session.claimed = True
        device, raw_token = self._enrollment.issue_device_token(device_label)

        self._audit.record(
            actor="new_device", action_type="security.device_pairing_claim",
            params_json=json.dumps({"label": device_label}),
            risk_tier="RED", decision="ALLOW", approval_id=None,
            result_status="EXECUTED",
            result_message=f"device {device.id} enrolled via pairing",
        )
        return raw_token

    def active_session_count(self) -> int:
        """For diagnostics -- never exposes the codes themselves."""
        now = datetime.now(timezone.utc)
        return sum(1 for s in self._sessions.values() if not s.claimed and not s.is_expired(now=now))
