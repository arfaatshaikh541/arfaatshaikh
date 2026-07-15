import uuid

import pytest

from core.config import settings
from db.session import set_tenant_context
from modules.credential_vault.adapters.base import EncryptedSecret
from modules.credential_vault.adapters.local import LocalEnvelopeVaultAdapter
from modules.credential_vault.service import (
    get_decrypted_secret,
    revoke_credential,
    rotate_credential,
    store_credential,
)


def test_local_adapter_roundtrip():
    adapter = LocalEnvelopeVaultAdapter(settings)
    secret = adapter.encrypt(b"top-secret-api-key")
    assert secret.ciphertext != b"top-secret-api-key"
    assert adapter.decrypt(secret) == b"top-secret-api-key"


def test_local_adapter_detects_tampering():
    adapter = LocalEnvelopeVaultAdapter(settings)
    secret = adapter.encrypt(b"top-secret-api-key")
    tampered = EncryptedSecret(
        ciphertext=secret.ciphertext[:-1] + bytes([secret.ciphertext[-1] ^ 0xFF]),
        nonce=secret.nonce,
        key_version=secret.key_version,
        wrapped_dek=secret.wrapped_dek,
    )
    with pytest.raises(Exception):
        adapter.decrypt(tampered)


def test_different_secrets_produce_different_ciphertext():
    adapter = LocalEnvelopeVaultAdapter(settings)
    a = adapter.encrypt(b"same-plaintext")
    b = adapter.encrypt(b"same-plaintext")
    # Random nonce/DEK per call — encrypting identical plaintext twice must
    # not produce identical ciphertext (defeats pattern-matching on stored
    # secrets).
    assert a.ciphertext != b.ciphertext


@pytest.mark.asyncio(loop_scope="session")
async def test_store_credential_never_persists_plaintext(db):
    tenant_id = uuid.uuid4()
    async with db.begin():
        await set_tenant_context(db, tenant_id)
        from modules.tenancy.models import Tenant

        db.add(
            Tenant(id=tenant_id, name="Vault Test Co", slug=f"vault-{tenant_id.hex[:8]}", status="active")
        )
        await db.flush()

        credential = await store_credential(
            db,
            tenant_id=tenant_id,
            provider_key="mock_identity",
            label="Test credential",
            secret_plaintext="hunter2-super-secret",
            created_by_user_id=uuid.uuid4(),
        )
        assert b"hunter2-super-secret" not in credential.ciphertext
        assert credential.health_status == "healthy"

        plaintext = await get_decrypted_secret(db, credential.id)
        assert plaintext == "hunter2-super-secret"


@pytest.mark.asyncio(loop_scope="session")
async def test_rotate_and_revoke_credential(db):
    tenant_id = uuid.uuid4()
    async with db.begin():
        await set_tenant_context(db, tenant_id)
        from modules.tenancy.models import Tenant

        db.add(
            Tenant(id=tenant_id, name="Rotate Test Co", slug=f"rotate-{tenant_id.hex[:8]}", status="active")
        )
        await db.flush()

        credential = await store_credential(
            db,
            tenant_id=tenant_id,
            provider_key="mock_identity",
            label="Rotatable",
            secret_plaintext="original-secret",
            created_by_user_id=uuid.uuid4(),
        )

        await rotate_credential(
            db, credential_id=credential.id, tenant_id=tenant_id, new_secret_plaintext="rotated-secret"
        )
        assert await get_decrypted_secret(db, credential.id) == "rotated-secret"
        assert credential.rotated_at is not None

        await revoke_credential(db, credential_id=credential.id, tenant_id=tenant_id)
        assert credential.revoked_at is not None
        assert credential.health_status == "revoked"

        with pytest.raises(Exception):
            await get_decrypted_secret(db, credential.id)
