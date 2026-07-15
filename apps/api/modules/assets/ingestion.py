"""Asset-graph ingestion: turns a connector's `NormalizedRecord` stream
into `Asset`/`AssetIdentifier` rows, with change tracking and
relationship resolution. Idempotent — running the same sync twice with
unchanged upstream data produces zero new `AssetChange` rows."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from gridkeep_connector_sdk import NormalizedRecord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.assets.models import (
    Asset,
    AssetChange,
    AssetIdentifier,
    AssetRelationship,
    AssetType,
)

# Maps a connector's NormalizedRecord.record_type onto a seeded AssetType
# key. Record types with no entry here (e.g. "threat_intel.indicator")
# are not assets and are intentionally skipped — that data belongs to a
# different subsystem (Milestone 6: Threat Intelligence).
RECORD_TYPE_TO_ASSET_TYPE_KEY: dict[str, str] = {
    "identity.user": "identity_user",
    "endpoint.device": "endpoint_device",
    "cloud.account": "cloud_account",
    "cloud.resource": "cloud_resource",
    "backup.job": "backup_job",
}


@dataclass
class IngestSummary:
    processed: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    relationships_created: int = 0
    relationships_updated: int = 0
    errors: list[str] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(UTC)


def _serialize(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, default=str)


async def _get_asset_type_map(session: AsyncSession) -> dict[str, AssetType]:
    result = await session.execute(select(AssetType))
    return {row.key: row for row in result.scalars().all()}


async def _find_asset_by_identifier(
    session: AsyncSession, *, tenant_id: uuid.UUID, identifier_type: str, identifier_value: str
) -> Asset | None:
    identifier = (
        await session.execute(
            select(AssetIdentifier).where(
                AssetIdentifier.tenant_id == tenant_id,
                AssetIdentifier.identifier_type == identifier_type,
                AssetIdentifier.identifier_value == identifier_value,
            )
        )
    ).scalar_one_or_none()
    if identifier is None:
        return None
    return await session.get(Asset, identifier.asset_id)


async def _ingest_one_record(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    tenant_integration_id: uuid.UUID,
    provider_id: str,
    record: NormalizedRecord,
    asset_type: AssetType,
    summary: IngestSummary,
) -> Asset:
    existing = await _find_asset_by_identifier(
        session,
        tenant_id=tenant_id,
        identifier_type=record.identifier_type,
        identifier_value=record.identifier_value,
    )

    if existing is None:
        asset = Asset(
            tenant_id=tenant_id,
            asset_type_id=asset_type.id,
            tenant_integration_id=tenant_integration_id,
            display_name=record.display_name,
            source=provider_id,
            confidence=1.0,
            attributes=record.attributes,
            last_observed_at=record.observed_at,
            last_assessed_at=None,
        )
        session.add(asset)
        await session.flush()
        session.add(
            AssetIdentifier(
                tenant_id=tenant_id,
                asset_id=asset.id,
                identifier_type=record.identifier_type,
                identifier_value=record.identifier_value,
            )
        )
        summary.created += 1
        return asset

    # Existing asset: diff attributes field-by-field and write AssetChange
    # rows only for fields that actually changed — never a blind overwrite.
    changed = False
    old_attributes = dict(existing.attributes or {})
    for key, new_value in record.attributes.items():
        old_value = old_attributes.get(key)
        if old_value != new_value:
            session.add(
                AssetChange(
                    tenant_id=tenant_id,
                    asset_id=existing.id,
                    tenant_integration_id=tenant_integration_id,
                    field_name=key,
                    old_value=_serialize(old_value),
                    new_value=_serialize(new_value),
                    changed_at=record.observed_at,
                )
            )
            changed = True
    if changed:
        existing.attributes = {**old_attributes, **record.attributes}

    if existing.display_name != record.display_name:
        session.add(
            AssetChange(
                tenant_id=tenant_id,
                asset_id=existing.id,
                tenant_integration_id=tenant_integration_id,
                field_name="display_name",
                old_value=existing.display_name,
                new_value=record.display_name,
                changed_at=record.observed_at,
            )
        )
        existing.display_name = record.display_name
        changed = True

    if changed:
        summary.updated += 1

    existing.last_observed_at = record.observed_at
    existing.tenant_integration_id = tenant_integration_id
    return existing


async def _resolve_relationship(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    provider_id: str,
    from_asset: Asset,
    relationship_type: str,
    target_identifier_type: str,
    target_identifier_value: str,
    observed_at: datetime,
    summary: IngestSummary,
) -> None:
    target_asset = await _find_asset_by_identifier(
        session,
        tenant_id=tenant_id,
        identifier_type=target_identifier_type,
        identifier_value=target_identifier_value,
    )
    if target_asset is None:
        # Target hasn't been ingested (yet, or ever) — nothing to link to.
        # Not an error: a future sync may introduce the target asset.
        return

    existing_edge = (
        await session.execute(
            select(AssetRelationship).where(
                AssetRelationship.tenant_id == tenant_id,
                AssetRelationship.from_asset_id == from_asset.id,
                AssetRelationship.to_asset_id == target_asset.id,
                AssetRelationship.relationship_type == relationship_type,
            )
        )
    ).scalar_one_or_none()

    if existing_edge is None:
        session.add(
            AssetRelationship(
                tenant_id=tenant_id,
                from_asset_id=from_asset.id,
                to_asset_id=target_asset.id,
                relationship_type=relationship_type,
                source=provider_id,
                confidence=1.0,
                observed_at=observed_at,
            )
        )
        summary.relationships_created += 1
    else:
        existing_edge.observed_at = observed_at
        summary.relationships_updated += 1


async def ingest_sync_records(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    tenant_integration_id: uuid.UUID,
    provider_id: str,
    records: list[NormalizedRecord],
) -> IngestSummary:
    """Two passes: (1) upsert every asset so every identifier in this
    batch resolves to a row, (2) resolve relationships now that both
    endpoints of any same-batch edge exist."""
    summary = IngestSummary()
    asset_types_by_key = await _get_asset_type_map(session)

    ingested_assets: list[tuple[Asset, NormalizedRecord]] = []
    for record in records:
        summary.processed += 1
        asset_type_key = RECORD_TYPE_TO_ASSET_TYPE_KEY.get(record.record_type)
        if asset_type_key is None or asset_type_key not in asset_types_by_key:
            summary.skipped += 1
            continue
        asset = await _ingest_one_record(
            session,
            tenant_id=tenant_id,
            tenant_integration_id=tenant_integration_id,
            provider_id=provider_id,
            record=record,
            asset_type=asset_types_by_key[asset_type_key],
            summary=summary,
        )
        ingested_assets.append((asset, record))

    await session.flush()

    for asset, record in ingested_assets:
        for rel in record.relationships:
            await _resolve_relationship(
                session,
                tenant_id=tenant_id,
                provider_id=provider_id,
                from_asset=asset,
                relationship_type=rel.relationship_type,
                target_identifier_type=rel.target_identifier_type,
                target_identifier_value=rel.target_identifier_value,
                observed_at=record.observed_at,
                summary=summary,
            )

    await session.flush()
    return summary
