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
    with a locally-configured master key. Used in development and in this
    Milestone 1 baseline.

    PRODUCTION implementation: a real secrets-manager-backed adapter
    (AWS Secrets Manager / GCP Secret Manager / Azure Key Vault / Vault)
    satisfying this same interface — not built in Milestone 1. Selecting it
    is an environment-driven wiring decision (core.config), never an
    application-logic branch.
    """

    @abstractmethod
    def encrypt(self, plaintext: bytes) -> EncryptedSecret: ...

    @abstractmethod
    def decrypt(self, secret: EncryptedSecret) -> bytes: ...

    @abstractmethod
    def current_key_version(self) -> int: ...
