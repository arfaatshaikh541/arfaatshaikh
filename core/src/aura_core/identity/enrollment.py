"""Owner enrollment and device trust: first-run identity creation plus a
persisted, hashed session token, so re-running the CLI or calling the API
from an already-trusted device never requires logging in again (section
9's "no re-auth every launch").

The raw token is shown to the owner exactly once, at issuance, and only
ever stored as a SHA-256 hash thereafter -- the same "never persist a
secret you can avoid persisting" discipline the Credential Broker already
follows elsewhere in this codebase. Protecting the on-disk token file with
the OS's real secret store (Windows DPAPI) is REQUIRES_WINDOWS_RUNTIME and
out of scope here; token_store.py protects it with owner-only file
permissions instead, which is real but weaker than DPAPI.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from ..memory.schema_migration import ensure_schema
from .models import DeviceTrust, Owner


class AlreadyEnrolledError(RuntimeError):
    pass


class NotEnrolledError(RuntimeError):
    pass


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


_PIN_ITERATIONS = 200_000


def _hash_pin(raw_pin: str, salt: bytes, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", raw_pin.encode(), salt, iterations).hex()


class EnrollmentEngine:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(database_url, connect_args=connect_args)
        ensure_schema(self._engine)
        self._Session = sessionmaker(bind=self._engine)

    def is_enrolled(self) -> bool:
        with self._Session() as session:
            return session.execute(select(Owner)).first() is not None

    def enroll_owner(self, display_name: str, *, device_label: str = "primary") -> tuple[Owner, str]:
        """Creates the one and only Owner plus its first trusted device.
        A one-time, first-run action -- raises AlreadyEnrolledError rather
        than silently minting a second owner identity if called again."""
        with self._Session() as session:
            if session.execute(select(Owner)).first() is not None:
                raise AlreadyEnrolledError("an owner is already enrolled on this installation")

            owner = Owner(display_name=display_name)
            session.add(owner)
            session.flush()

            raw_token = secrets.token_urlsafe(32)
            device = DeviceTrust(owner_id=owner.id, label=device_label, token_hash=_hash_token(raw_token))
            session.add(device)
            session.commit()
            session.refresh(owner)
            return owner, raw_token

    def issue_device_token(self, device_label: str) -> tuple[DeviceTrust, str]:
        """Trusts another device (a second machine, or re-trusting after a
        revoke) under the existing owner."""
        with self._Session() as session:
            owner = session.execute(select(Owner)).scalars().first()
            if owner is None:
                raise NotEnrolledError("no owner enrolled yet -- call enroll_owner() first")

            raw_token = secrets.token_urlsafe(32)
            device = DeviceTrust(owner_id=owner.id, label=device_label, token_hash=_hash_token(raw_token))
            session.add(device)
            session.commit()
            session.refresh(device)
            return device, raw_token

    def verify_token(self, raw_token: str) -> DeviceTrust | None:
        """The only way to check a token, since the raw value is never
        stored. Updates last_seen_at on success so `aura devices list`
        reflects real recency."""
        token_hash = _hash_token(raw_token)
        with self._Session() as session:
            device = session.execute(
                select(DeviceTrust).where(DeviceTrust.token_hash == token_hash)
            ).scalars().first()
            if device is None or device.revoked_at is not None:
                return None
            device.last_seen_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(device)
            return device

    def list_devices(self) -> list[DeviceTrust]:
        with self._Session() as session:
            return list(session.execute(select(DeviceTrust)).scalars().all())

    def owner_display_name(self) -> str | None:
        """Read-only convenience for surfaces that need to greet the
        owner by name (e.g. /identity/whoami) without exposing anything
        else about the Owner row. None before enrollment."""
        with self._Session() as session:
            owner = session.execute(select(Owner)).scalars().first()
            return owner.display_name if owner is not None else None

    def revoke_device(self, device_id: str) -> None:
        with self._Session() as session:
            device = session.get(DeviceTrust, device_id)
            if device is not None:
                device.revoked_at = datetime.now(timezone.utc)
                session.commit()

    def has_owner_pin(self) -> bool:
        with self._Session() as session:
            owner = session.execute(select(Owner)).scalars().first()
            return owner is not None and owner.pin_hash is not None

    def set_owner_pin(self, raw_pin: str) -> None:
        """Sets or replaces the owner's backend-elevation PIN. A fresh
        random salt every time, per standard password-hashing practice
        -- even a PIN change never reuses a prior salt."""
        with self._Session() as session:
            owner = session.execute(select(Owner)).scalars().first()
            if owner is None:
                raise NotEnrolledError("no owner enrolled yet -- call enroll_owner() first")

            salt = secrets.token_bytes(16)
            owner.pin_salt = salt.hex()
            owner.pin_iterations = _PIN_ITERATIONS
            owner.pin_hash = _hash_pin(raw_pin, salt, _PIN_ITERATIONS)
            session.commit()

    def verify_owner_pin(self, raw_pin: str) -> bool:
        """Constant-time comparison against the stored hash. Returns
        False both when no PIN has ever been configured and when the
        PIN presented is simply wrong -- the caller must never be able
        to distinguish "not set up" from "incorrect" through this
        method's return value alone (see identity/elevation.py, which
        is the only production caller)."""
        with self._Session() as session:
            owner = session.execute(select(Owner)).scalars().first()
            if owner is None or owner.pin_hash is None:
                return False
            salt = bytes.fromhex(owner.pin_salt)
            candidate = _hash_pin(raw_pin, salt, owner.pin_iterations)
            return hmac.compare_digest(candidate, owner.pin_hash)
