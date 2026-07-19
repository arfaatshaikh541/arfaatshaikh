from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class EncryptedSecret:
    ciphertext: bytes
    nonce: bytes
    key_version: int
    wrapped_dek: bytes


class VaultAdapter(ABC):
    """Provider-neutral secret-vault abstraction (architecture §11).

    LOCAL implementation: `LocalEnvelopeVaultAdapter` — envelope encryption
    with a locally-configured master key. Used in development and test
    only (Milestone 1 baseline; refused at boot in production since
    Milestone 32 — see `core/config.py:_validate_production_safety`).

    PRODUCTION implementation: `HashiCorpVaultAdapter` (Milestone 32,
    finding C-02) — real encryption-as-a-service via HashiCorp Vault's
    Transit secrets engine; the application never holds or derives key
    material. Selecting it is an environment-driven wiring decision
    (`core.config.settings.vault_adapter`, read by
    `modules/credential_vault/service.py:get_vault_adapter`), never an
    application-logic branch.
    """

    @abstractmethod
    def encrypt(self, plaintext: bytes) -> EncryptedSecret: ...

    @abstractmethod
    def decrypt(self, secret: EncryptedSecret) -> bytes: ...

    @abstractmethod
    def current_key_version(self) -> int: ...
