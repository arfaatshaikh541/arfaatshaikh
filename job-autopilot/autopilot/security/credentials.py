"""Credential storage service. Passwords are write-only through this API."""
from __future__ import annotations

import datetime as dt
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Credential, utcnow
from .vault import Vault, credential_context, get_vault


@dataclass(frozen=True)
class CredentialView:
    """Everything the UI/API may see about a credential. No secret material."""

    id: int
    platform_key: str
    label: str
    username: str | None
    mfa_mode: str
    key_id: str
    created_at: dt.datetime
    updated_at: dt.datetime
    last_used_at: dt.datetime | None
    rotate_after_days: int | None

    @property
    def rotation_due(self) -> bool:
        if not self.rotate_after_days:
            return False
        return utcnow() - self.updated_at > dt.timedelta(days=self.rotate_after_days)


def _view(c: Credential) -> CredentialView:
    return CredentialView(
        c.id, c.platform_key, c.label, c.username, c.mfa_mode, c.key_id,
        c.created_at, c.updated_at, c.last_used_at, c.rotate_after_days,
    )


def store_credential(
    s: Session,
    *,
    user_id: int,
    platform_key: str,
    username: str | None,
    secret: str,
    label: str = "default",
    mfa_mode: str = "none",
    rotate_after_days: int | None = None,
    vault: Vault | None = None,
) -> CredentialView:
    if not secret:
        raise ValueError("Secret must not be empty")
    vault = vault or get_vault()
    ctx = credential_context(platform_key, user_id, label)
    blob = vault.encrypt_str(secret, ctx)
    c = s.scalar(
        select(Credential).where(
            Credential.user_id == user_id, Credential.platform_key == platform_key, Credential.label == label
        )
    )
    if c is None:
        c = Credential(user_id=user_id, platform_key=platform_key, label=label)
        s.add(c)
    c.username = username
    c.blob = blob
    c.key_id = vault.current_key_id
    c.mfa_mode = mfa_mode
    c.rotate_after_days = rotate_after_days
    c.updated_at = utcnow()
    s.flush()
    return _view(c)


def list_credentials(s: Session, user_id: int) -> list[CredentialView]:
    rows = s.scalars(select(Credential).where(Credential.user_id == user_id).order_by(Credential.platform_key))
    return [_view(c) for c in rows]


def get_credential_view(s: Session, user_id: int, platform_key: str, label: str = "default") -> CredentialView | None:
    c = s.scalar(
        select(Credential).where(
            Credential.user_id == user_id, Credential.platform_key == platform_key, Credential.label == label
        )
    )
    return _view(c) if c else None


def delete_credential(s: Session, user_id: int, credential_id: int) -> bool:
    c = s.get(Credential, credential_id)
    if c is None or c.user_id != user_id:
        return False
    s.delete(c)
    return True


@contextmanager
def use_credential(
    s: Session, user_id: int, platform_key: str, label: str = "default", vault: Vault | None = None
) -> Iterator[tuple[str | None, str]]:
    """Yield ``(username, secret)`` for the duration of the block (worker-only)."""
    vault = vault or get_vault()
    c = s.scalar(
        select(Credential).where(
            Credential.user_id == user_id, Credential.platform_key == platform_key, Credential.label == label
        )
    )
    if c is None:
        raise LookupError(f"No credential configured for {platform_key}/{label}")
    with vault.use_secret(c.blob, credential_context(platform_key, user_id, label)) as secret:
        c.last_used_at = utcnow()
        yield c.username, secret


def rotate_master_key(s: Session, vault: Vault) -> int:
    """Re-wrap every stored secret under the vault's current key. Returns count."""
    n = 0
    for c in s.scalars(select(Credential)):
        if c.key_id != vault.current_key_id:
            ctx = credential_context(c.platform_key, c.user_id, c.label).encode()
            c.blob = vault.rewrap(c.blob, ctx)
            c.key_id = vault.current_key_id
            n += 1
    from ..models import PlatformSession

    for ps in s.scalars(select(PlatformSession)):
        if ps.key_id != vault.current_key_id:
            ctx = f"platform_session:{ps.platform_key}:{ps.id}".encode()
            ps.storage_state_blob = vault.rewrap(ps.storage_state_blob, ctx)
            ps.key_id = vault.current_key_id
            n += 1
    return n
