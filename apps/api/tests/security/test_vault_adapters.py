"""Hardening-programme Milestone 5 (finding C-02) — proves
`HashiCorpVaultAdapter` against a REAL local HashiCorp Vault server (dev
mode: in-memory storage, auto-unsealed), not a mock. Started as a
module-scoped subprocess fixture, the same pattern `tests/conftest.py`
already uses for a real local SMTP server (Milestone 28). Skipped
entirely (not failed) if no `vault` binary is on PATH, so the rest of the
suite stays runnable in an environment that hasn't installed it — CI and
this module's own requirements install it explicitly (see
`.github/workflows/ci.yml`)."""

from __future__ import annotations

import shutil
import socket
import subprocess
import time

import hvac
import pytest

from core.config import Settings
from core.errors import VaultUnavailableError
from modules.credential_vault.adapters.base import EncryptedSecret
from modules.credential_vault.adapters.hashicorp_vault import HashiCorpVaultAdapter

_VAULT_BINARY = shutil.which("vault")
pytestmark = pytest.mark.skipif(_VAULT_BINARY is None, reason="vault binary not on PATH")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def vault_server():
    """A real `vault server -dev` process — in-memory storage, no TLS,
    auto-unsealed with a fixed root token — bound to a free local port so
    it never collides with a developer's own Vault instance on the
    standard 8200."""
    port = _free_port()
    addr = f"http://127.0.0.1:{port}"
    token = "gridkeep-test-vault-root-token"
    proc = subprocess.Popen(
        [
            _VAULT_BINARY, "server", "-dev",
            f"-dev-root-token-id={token}",
            f"-dev-listen-address=127.0.0.1:{port}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("vault dev server did not start listening in time")
        # The port accepting connections doesn't guarantee Vault has
        # finished its post-unseal setup yet — give the HTTP API itself a
        # moment before the first real request.
        time.sleep(0.5)

        # Enabling a secrets engine mount (`sys/mounts/*`) is an
        # infrastructure-provisioning operation, not something
        # `HashiCorpVaultAdapter` does itself — a real deployment's
        # application token is scoped to a policy covering only
        # `transit/{encrypt,decrypt,keys}/<key-name>`, which does not
        # include `sys/mounts` capability (least privilege: the app can
        # use its own key, not reconfigure Vault's engine topology). This
        # mirrors what `docs/deployment-production.md` documents as an
        # ops-side setup step, done here with the dev server's root token
        # standing in for that provisioning process.
        hvac.Client(url=addr, token=token).sys.enable_secrets_engine(
            backend_type="transit", path="transit"
        )

        yield {"addr": addr, "token": token}
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def _settings(
    vault_server, *, token: str | None = None, key_name: str = "gridkeep-vault-test-key"
) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        vault_adapter="vault",
        vault_hashicorp_addr=vault_server["addr"],
        vault_hashicorp_token=token if token is not None else vault_server["token"],
        vault_hashicorp_transit_key_name=key_name,
        vault_local_master_key="test-only-master-key-do-not-use-elsewhere-00000",
    )


def test_encrypt_decrypt_round_trips_through_real_vault(vault_server):
    adapter = HashiCorpVaultAdapter(_settings(vault_server, key_name="round-trip-key"))
    plaintext = b"a real integration credential secret"

    encrypted = adapter.encrypt(plaintext)
    assert encrypted.ciphertext.startswith(b"vault:v")
    # Vault's own envelope format carries version + nonce internally —
    # this adapter never derives or stores either itself, unlike the
    # local adapter's DEK-wrapping scheme.
    assert encrypted.nonce == b""
    assert encrypted.wrapped_dek == b""

    decrypted = adapter.decrypt(encrypted)
    assert decrypted == plaintext


def test_application_never_sees_vault_plaintext_ciphertext_is_opaque(vault_server):
    """The whole point of encryption-as-a-service: the stored ciphertext
    is Vault's own token, not something this codebase's crypto touches —
    proven by asserting the plaintext never appears as a substring of
    what actually gets persisted."""
    adapter = HashiCorpVaultAdapter(_settings(vault_server, key_name="opaque-ciphertext-key"))
    plaintext = b"another-distinct-secret-value-12345"

    encrypted = adapter.encrypt(plaintext)
    assert plaintext not in encrypted.ciphertext


def test_current_key_version_matches_a_fresh_key(vault_server):
    adapter = HashiCorpVaultAdapter(_settings(vault_server, key_name="version-check-key"))
    assert adapter.current_key_version() == 1

    encrypted = adapter.encrypt(b"versioned secret")
    assert encrypted.key_version == 1


def test_tampered_ciphertext_fails_to_decrypt(vault_server):
    """Real proof the ciphertext is authenticated (AES-256-GCM under the
    hood) — Vault itself rejects a corrupted token rather than this
    codebase's own crypto catching it, since this adapter never touches
    raw key material to verify anything locally."""
    adapter = HashiCorpVaultAdapter(_settings(vault_server, key_name="tamper-check-key"))
    encrypted = adapter.encrypt(b"secret that will be tampered with")

    tampered = EncryptedSecret(
        ciphertext=encrypted.ciphertext[:-4] + b"AAAA",
        nonce=encrypted.nonce,
        key_version=encrypted.key_version,
        wrapped_dek=encrypted.wrapped_dek,
    )
    with pytest.raises(VaultUnavailableError):
        adapter.decrypt(tampered)


def test_wrong_token_is_refused(vault_server):
    """A misconfigured or revoked VAULT_HASHICORP_TOKEN must fail loudly
    (a 503-class `VaultUnavailableError`, not a silent no-op or a crash
    with an unrelated exception type) — this is the failure mode a real
    deployment hits when a token expires or a policy is tightened."""
    settings = _settings(vault_server, token="totally-wrong-token", key_name="wrong-token-key")
    with pytest.raises(VaultUnavailableError):
        HashiCorpVaultAdapter(settings)


def test_unreachable_vault_server_raises_vault_unavailable_error():
    """No real server behind this address at all — proves the adapter
    distinguishes "Vault said no" (VaultError, tested above) from
    "couldn't reach Vault at all" (a bare requests exception), wrapping
    both into the same domain error so callers don't need to know the
    difference, but the boot-time construction itself still fails loudly
    rather than silently constructing a non-functional adapter."""
    settings = Settings(
        _env_file=None,
        environment="test",
        vault_adapter="vault",
        vault_hashicorp_addr="http://127.0.0.1:1",
        vault_hashicorp_token="irrelevant",
        vault_hashicorp_transit_key_name="unreachable-key",
        vault_local_master_key="test-only-master-key-do-not-use-elsewhere-00000",
    )
    with pytest.raises(VaultUnavailableError):
        HashiCorpVaultAdapter(settings)


def test_adapter_construction_is_idempotent_against_an_existing_key(vault_server):
    """Constructing a second adapter instance pointed at the same
    already-provisioned key must not fail or reset it — proves the
    create-or-converge behaviour `__init__` relies on (mirroring migration
    34016597f04f's own idempotent CREATE-OR-ALTER pattern for the
    `gridkeep_app` Postgres role) actually holds against a real server,
    not just Vault's documented API contract."""
    key_name = "idempotent-construction-key"
    first = HashiCorpVaultAdapter(_settings(vault_server, key_name=key_name))
    encrypted = first.encrypt(b"secret encrypted before the second construction")

    second = HashiCorpVaultAdapter(_settings(vault_server, key_name=key_name))
    assert second.decrypt(encrypted) == b"secret encrypted before the second construction"
    assert second.current_key_version() == 1
