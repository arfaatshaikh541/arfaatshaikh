"""Envelope encryption for credentials, session cookies, CV files and API keys.

Format of an encrypted blob (all binary):

    b"JAV1" | key_id(8 ascii) | wrap_nonce(12) | wrapped_dek(48) | nonce(12) | ciphertext+tag

* A fresh random 256-bit data-encryption key (DEK) is generated per blob.
* The DEK is wrapped with the master key (AES-256-GCM, AAD = key_id).
* The payload is encrypted with the DEK (AES-256-GCM, AAD = caller context,
  e.g. ``b"credential:linkedin:3"``) so a blob cannot be swapped between records.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import Config, get_config
from .redact import register_secret, unregister_secret

MAGIC = b"JAV1"
_KEY_ID_LEN = 8


class VaultError(Exception):
    pass


class VaultNotConfigured(VaultError):
    pass


def _decode_key(raw: str) -> bytes:
    raw = raw.strip()
    for decoder in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            key = decoder(raw + "=" * (-len(raw) % 4))
        except (binascii.Error, ValueError):
            continue
        if len(key) == 32:
            return key
    raise VaultError("Master key must be 32 bytes, base64 encoded (generate with `autopilot gen-master-key`).")


def key_id_for(key: bytes) -> str:
    return hashlib.sha256(b"jobap-key-id" + key).hexdigest()[:_KEY_ID_LEN]


def generate_master_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


@dataclass(frozen=True)
class _Key:
    key_id: str
    key: bytes


class Vault:
    def __init__(self, current: bytes, retired: list[bytes] | None = None):
        self._current = _Key(key_id_for(current), current)
        self._keys = {self._current.key_id: self._current}
        for k in retired or []:
            kk = _Key(key_id_for(k), k)
            self._keys.setdefault(kk.key_id, kk)

    @classmethod
    def from_config(cls, cfg: Config | None = None) -> "Vault":
        cfg = cfg or get_config()
        raw = cfg.master_key
        if cfg.master_key_file:
            p = Path(cfg.master_key_file)
            if not p.exists():
                raise VaultNotConfigured(f"Master key file {p} does not exist")
            raw = p.read_text()
        if not raw:
            raise VaultNotConfigured(
                "Credential vault NOT CONFIGURED: set JOBAP_MASTER_KEY_FILE or JOBAP_MASTER_KEY"
            )
        retired = [_decode_key(k) for k in cfg.old_master_keys.split(",") if k.strip()]
        return cls(_decode_key(raw), retired)

    @property
    def current_key_id(self) -> str:
        return self._current.key_id

    def encrypt(self, plaintext: bytes, context: bytes) -> bytes:
        dek = AESGCM.generate_key(bit_length=256)
        wrap_nonce = os.urandom(12)
        wrapped = AESGCM(self._current.key).encrypt(wrap_nonce, dek, self._current.key_id.encode())
        nonce = os.urandom(12)
        ct = AESGCM(dek).encrypt(nonce, plaintext, context)
        return MAGIC + self._current.key_id.encode() + wrap_nonce + wrapped + nonce + ct

    @staticmethod
    def blob_key_id(blob: bytes) -> str:
        if not blob.startswith(MAGIC):
            raise VaultError("Not a vault blob")
        return blob[4 : 4 + _KEY_ID_LEN].decode()

    def decrypt(self, blob: bytes, context: bytes) -> bytes:
        if not blob.startswith(MAGIC) or len(blob) < 4 + _KEY_ID_LEN + 12 + 48 + 12 + 16:
            raise VaultError("Corrupt vault blob")
        o = 4
        kid = blob[o : o + _KEY_ID_LEN].decode()
        o += _KEY_ID_LEN
        wrap_nonce = blob[o : o + 12]
        o += 12
        wrapped = blob[o : o + 48]
        o += 48
        nonce = blob[o : o + 12]
        o += 12
        ct = blob[o:]
        key = self._keys.get(kid)
        if key is None:
            raise VaultError(f"Blob encrypted with unknown key id {kid}; supply it in JOBAP_OLD_MASTER_KEYS")
        try:
            dek = AESGCM(key.key).decrypt(wrap_nonce, wrapped, kid.encode())
            return AESGCM(dek).decrypt(nonce, ct, context)
        except Exception as e:
            raise VaultError("Decryption failed (wrong key or tampered data)") from e

    def rewrap(self, blob: bytes, context: bytes) -> bytes:
        """Re-encrypt a blob under the current master key (rotation)."""
        return self.encrypt(self.decrypt(blob, context), context)

    def encrypt_str(self, value: str, context: str) -> bytes:
        return self.encrypt(value.encode(), context.encode())

    @contextmanager
    def use_secret(self, blob: bytes, context: str) -> Iterator[str]:
        """Decrypt a secret for the duration of the block.

        The plaintext is registered with the log redactor so it can never be
        written to logs, even by accident, while in use.
        """
        value = self.decrypt(blob, context.encode()).decode()
        register_secret(value)
        try:
            yield value
        finally:
            unregister_secret(value)

    def self_test(self) -> bool:
        probe = os.urandom(16)
        return self.decrypt(self.encrypt(probe, b"self-test"), b"self-test") == probe


def credential_context(platform_key: str, user_id: int, label: str) -> str:
    return f"credential:{user_id}:{platform_key}:{label}"


def get_vault() -> Vault:
    return Vault.from_config()


def vault_status() -> tuple[bool, str]:
    try:
        v = get_vault()
        ok = v.self_test()
        return ok, f"HEALTHY (key {v.current_key_id})" if ok else "SELF-TEST FAILED"
    except VaultNotConfigured as e:
        return False, f"NOT CONFIGURED: {e}"
    except VaultError as e:
        return False, f"ERROR: {e}"
