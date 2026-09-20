"""Credential Broker: minimal, real, in-process implementation.

No connector exists yet that needs a real external secret (that's
deferred, per the owner's explicit decision to keep high-risk connectors
interface-only for now). But the *pattern* is real and enforced starting
now: the Action Broker issues a short-lived, task-scoped token before every
handler execution and revokes it immediately after, so when a real
connector's secret exchange is added later, it plugs into this same
interface rather than agents inventing their own credential handling. See
docs/security/README.md#credential-vault.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class CredentialToken:
    token: str
    action_type: str
    scope: str
    issued_at: datetime
    expires_at: datetime
    revoked: bool = False

    def is_valid(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return not self.revoked and now < self.expires_at


class CredentialBroker:
    def __init__(self, default_ttl_seconds: int = 300) -> None:
        self._default_ttl = timedelta(seconds=default_ttl_seconds)
        self._issued: dict[str, CredentialToken] = {}

    def issue(self, action_type: str, scope: str, ttl_seconds: int | None = None) -> CredentialToken:
        now = datetime.now(timezone.utc)
        ttl = timedelta(seconds=ttl_seconds) if ttl_seconds is not None else self._default_ttl
        token = CredentialToken(
            token=secrets.token_urlsafe(24),
            action_type=action_type,
            scope=scope,
            issued_at=now,
            expires_at=now + ttl,
        )
        self._issued[token.token] = token
        return token

    def revoke(self, token: str) -> None:
        record = self._issued.get(token)
        if record is not None:
            record.revoked = True

    def revoke_all(self) -> int:
        count = 0
        for record in self._issued.values():
            if not record.revoked:
                record.revoked = True
                count += 1
        return count

    def is_valid(self, token: str) -> bool:
        record = self._issued.get(token)
        return record is not None and record.is_valid()
