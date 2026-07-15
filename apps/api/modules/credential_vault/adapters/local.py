from __future__ import annotations

import hashlib
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from core.config import Settings
from modules.credential_vault.adapters.base import EncryptedSecret, VaultAdapter

_NONCE_LEN = 12


class LocalEnvelopeVaultAdapter(VaultAdapter):
    """LOCAL / DEVELOPMENT adapter. Envelope encryption: a random 256-bit
    Data Encryption Key (DEK) encrypts the secret with AES-256-GCM; the DEK
    itself is wrapped by a Key Encryption Key (KEK) derived (HKDF-SHA256)
    from `settings.vault_local_master_key`. Neither the DEK nor the
    plaintext secret is ever persisted unencrypted.

    NOT for production use — production deployments must configure a real
    secrets-manager-backed adapter implementing the same VaultAdapter
    interface (see adapters/base.py)."""

    def __init__(self, settings: Settings, *, key_version: int = 1) -> None:
        self._master_key_material = settings.vault_local_master_key.encode("utf-8")
        self._key_version = key_version

    def current_key_version(self) -> int:
        return self._key_version

    def _derive_kek(self, key_version: int) -> bytes:
        salt = hashlib.sha256(f"gridkeep-vault-kek-v{key_version}".encode()).digest()
        return HKDF(
            algorithm=hashes.SHA256(), length=32, salt=salt, info=b"gridkeep-credential-vault"
        ).derive(self._master_key_material)

    def encrypt(self, plaintext: bytes) -> EncryptedSecret:
        dek = os.urandom(32)
        data_nonce = os.urandom(_NONCE_LEN)
        ciphertext = AESGCM(dek).encrypt(data_nonce, plaintext, None)

        kek = self._derive_kek(self._key_version)
        wrap_nonce = os.urandom(_NONCE_LEN)
        wrapped_dek_body = AESGCM(kek).encrypt(wrap_nonce, dek, None)

        return EncryptedSecret(
            ciphertext=ciphertext,
            nonce=data_nonce,
            key_version=self._key_version,
            wrapped_dek=wrap_nonce + wrapped_dek_body,
        )

    def decrypt(self, secret: EncryptedSecret) -> bytes:
        kek = self._derive_kek(secret.key_version)
        wrap_nonce, wrapped_dek_body = (
            secret.wrapped_dek[:_NONCE_LEN],
            secret.wrapped_dek[_NONCE_LEN:],
        )
        dek = AESGCM(kek).decrypt(wrap_nonce, wrapped_dek_body, None)
        return AESGCM(dek).decrypt(secret.nonce, secret.ciphertext, None)
