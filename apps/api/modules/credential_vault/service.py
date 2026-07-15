from __future__ import annotations

import uuid
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings as app_settings
from core.errors import NotFoundError
from modules.credential_vault.adapters.base import EncryptedSecret, VaultAdapter
from modules.credential_vault.adapters.local import LocalEnvelopeVaultAdapter
from modules.credential_vault.models import IntegrationCredential


@lru_cache
def get_vault_adapter() -> VaultAdapter:
    """Environment-driven adapter selection — never an application-logic
    branch. Production deployments point this at a secrets-manager-backed
    adapter satisfying the same VaultAdapter interface (architecture §11);
    that adapter is out of scope for Milestone 1."""
    return LocalEnvelopeVaultAdapter(app_settings)


def _now() -> datetime:
    return datetime.now(UTC)


async def store_credential(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    provider_key: str,
    label: str,
    secret_plaintext: str,
    created_by_user_id: uuid.UUID,
) -> IntegrationCredential:
    encrypted = get_vault_adapter().encrypt(secret_plaintext.encode("utf-8"))
    credential = IntegrationCredential(
        tenant_id=tenant_id,
        provider_key=provider_key,
        label=label,
        ciphertext=encrypted.ciphertext,
        nonce=encrypted.nonce,
        wrapped_dek=encrypted.wrapped_dek,
        key_version=encrypted.key_version,
        health_status="healthy",
        created_by_user_id=created_by_user_id,
    )
    session.add(credential)
    await session.flush()
    return credential


async def get_decrypted_secret(session: AsyncSession, credential_id: uuid.UUID) -> str:
    """Internal use only (connector sync/action-execution workers in later
    milestones) — never called from an API route, never returned in an API
    response. Retrieval marks `last_used_at` for the integration-health
    view."""
    credential = (
        await session.execute(
            select(IntegrationCredential).where(IntegrationCredential.id == credential_id)
        )
    ).scalar_one_or_none()
    if credential is None or credential.revoked_at is not None:
        raise NotFoundError("Credential not found or has been revoked.")

    plaintext = get_vault_adapter().decrypt(
        EncryptedSecret(
            ciphertext=credential.ciphertext,
            nonce=credential.nonce,
            key_version=credential.key_version,
            wrapped_dek=credential.wrapped_dek,
        )
    )
    credential.last_used_at = _now()
    await session.flush()
    return plaintext.decode("utf-8")


async def rotate_credential(
    session: AsyncSession, *, credential_id: uuid.UUID, tenant_id: uuid.UUID, new_secret_plaintext: str
) -> IntegrationCredential:
    credential = (
        await session.execute(
            select(IntegrationCredential).where(
                IntegrationCredential.id == credential_id, IntegrationCredential.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if credential is None:
        raise NotFoundError("Credential not found.")

    encrypted = get_vault_adapter().encrypt(new_secret_plaintext.encode("utf-8"))
    credential.ciphertext = encrypted.ciphertext
    credential.nonce = encrypted.nonce
    credential.wrapped_dek = encrypted.wrapped_dek
    credential.key_version = encrypted.key_version
    credential.rotated_at = _now()
    credential.health_status = "healthy"
    await session.flush()
    return credential


async def revoke_credential(
    session: AsyncSession, *, credential_id: uuid.UUID, tenant_id: uuid.UUID
) -> IntegrationCredential:
    credential = (
        await session.execute(
            select(IntegrationCredential).where(
                IntegrationCredential.id == credential_id, IntegrationCredential.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if credential is None:
        raise NotFoundError("Credential not found.")

    credential.revoked_at = _now()
    credential.health_status = "revoked"
    await session.flush()
    return credential


async def list_credentials(session: AsyncSession, *, tenant_id: uuid.UUID) -> list[IntegrationCredential]:
    result = await session.execute(
        select(IntegrationCredential).where(IntegrationCredential.tenant_id == tenant_id)
    )
    return list(result.scalars().all())
