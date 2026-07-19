from __future__ import annotations

import base64

import hvac
import requests
from hvac.exceptions import VaultError

from core.config import Settings
from core.errors import VaultUnavailableError
from modules.credential_vault.adapters.base import EncryptedSecret, VaultAdapter

_UNREACHABLE_MESSAGE = (
    "Could not reach the HashiCorp Vault server — check VAULT_HASHICORP_ADDR, network "
    "connectivity, and that Vault is unsealed."
)


class HashiCorpVaultAdapter(VaultAdapter):
    """PRODUCTION adapter (hardening-programme Milestone 5, finding C-02):
    encryption-as-a-service via HashiCorp Vault's Transit secrets engine.

    Unlike `LocalEnvelopeVaultAdapter`, this application never holds,
    derives, or persists any key material at all — every `encrypt`/
    `decrypt` call is a real network request to Vault, which performs
    AES-256-GCM under a key Vault itself generates, stores, rotates, and
    never returns to callers (`exportable=false` on the key this adapter
    provisions). Vault's own response format (`vault:v<N>:<base64>`) is
    self-describing and already carries its key version and nonce, so
    `EncryptedSecret.nonce`/`.wrapped_dek` — meaningful for the local
    adapter's own DEK-wrapping scheme — are unused (`b""`) here; the whole
    opaque token lives in `.ciphertext`.

    Chosen over a specific cloud KMS (AWS/GCP/Azure) because it's the one
    option `adapters/base.py`'s own docstring lists that isn't tied to a
    single cloud provider, matching this codebase's actual deployment
    target today: a self-hosted docker-compose stack with no cloud account
    to bind a KMS to. Swapping to a cloud KMS later means adding a sibling
    adapter satisfying the same `VaultAdapter` interface — not touching
    this one or any of its callers."""

    def __init__(self, settings: Settings) -> None:
        if not settings.vault_hashicorp_addr or not settings.vault_hashicorp_token:
            raise ValueError(
                "VAULT_HASHICORP_ADDR and VAULT_HASHICORP_TOKEN must both be set to use the "
                "HashiCorp Vault adapter (VAULT_ADAPTER=vault)."
            )
        self._client = hvac.Client(url=settings.vault_hashicorp_addr, token=settings.vault_hashicorp_token)
        self._mount_point = settings.vault_hashicorp_mount_point
        self._key_name = settings.vault_hashicorp_transit_key_name
        # Idempotent (Vault returns the existing key's metadata unchanged
        # if it's already present — verified against a real dev-mode Vault
        # server, not assumed from documentation) — the same
        # create-or-converge pattern migration 34016597f04f already uses
        # for the `gridkeep_app` Postgres role. `exportable=False` (Vault's
        # own default) means even an operator with Vault admin access
        # cannot extract the raw key material through this API — only
        # encrypt/decrypt operations are possible, ever.
        try:
            self._client.secrets.transit.create_key(name=self._key_name, mount_point=self._mount_point)
        except VaultError as exc:
            raise VaultUnavailableError(f"Could not provision the Vault transit key: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            raise VaultUnavailableError(_UNREACHABLE_MESSAGE) from exc

    def current_key_version(self) -> int:
        try:
            info = self._client.secrets.transit.read_key(name=self._key_name, mount_point=self._mount_point)
        except VaultError as exc:
            raise VaultUnavailableError(f"Vault key-metadata request failed: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            raise VaultUnavailableError(_UNREACHABLE_MESSAGE) from exc
        return int(info["data"]["latest_version"])

    def encrypt(self, plaintext: bytes) -> EncryptedSecret:
        try:
            resp = self._client.secrets.transit.encrypt_data(
                name=self._key_name,
                mount_point=self._mount_point,
                plaintext=base64.b64encode(plaintext).decode("ascii"),
            )
        except VaultError as exc:
            raise VaultUnavailableError(f"Vault encrypt request failed: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            raise VaultUnavailableError(_UNREACHABLE_MESSAGE) from exc

        ciphertext_token: str = resp["data"]["ciphertext"]
        return EncryptedSecret(
            ciphertext=ciphertext_token.encode("ascii"),
            nonce=b"",
            key_version=int(resp["data"]["key_version"]),
            wrapped_dek=b"",
        )

    def decrypt(self, secret: EncryptedSecret) -> bytes:
        try:
            resp = self._client.secrets.transit.decrypt_data(
                name=self._key_name,
                mount_point=self._mount_point,
                ciphertext=secret.ciphertext.decode("ascii"),
            )
        except VaultError as exc:
            raise VaultUnavailableError(f"Vault decrypt request failed: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            raise VaultUnavailableError(_UNREACHABLE_MESSAGE) from exc

        return base64.b64decode(resp["data"]["plaintext"])
