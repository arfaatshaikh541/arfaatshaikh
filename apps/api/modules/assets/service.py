from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.errors import NotFoundError
from modules.assets.models import (
    Asset,
    AssetChange,
    AssetOwner,
    AssetRelationship,
    AssetTag,
    AssetType,
)
from modules.identity.models import User


def _now() -> datetime:
    return datetime.now(UTC)


async def list_assets(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    asset_type_key: str | None = None,
    criticality: str | None = None,
    search: str | None = None,
) -> list[tuple[Asset, AssetType]]:
    query = (
        select(Asset, AssetType)
        .join(AssetType, AssetType.id == Asset.asset_type_id)
        .where(Asset.tenant_id == tenant_id)
    )
    if asset_type_key:
        query = query.where(AssetType.key == asset_type_key)
    if criticality:
        query = query.where(Asset.criticality == criticality)
    if search:
        query = query.where(Asset.display_name.ilike(f"%{search}%"))
    query = query.order_by(Asset.last_observed_at.desc())
    result = await session.execute(query)
    return [(asset, asset_type) for asset, asset_type in result.all()]


async def get_asset_detail(session: AsyncSession, *, tenant_id: uuid.UUID, asset_id: uuid.UUID):
    row = (
        await session.execute(
            select(Asset, AssetType)
            .join(AssetType, AssetType.id == Asset.asset_type_id)
            .options(selectinload(Asset.identifiers))
            .where(Asset.id == asset_id, Asset.tenant_id == tenant_id)
        )
    ).one_or_none()
    if row is None:
        raise NotFoundError("Asset not found.")
    asset, asset_type = row

    outbound = (
        await session.execute(
            select(AssetRelationship, Asset.display_name)
            .join(Asset, Asset.id == AssetRelationship.to_asset_id)
            .where(AssetRelationship.tenant_id == tenant_id, AssetRelationship.from_asset_id == asset_id)
        )
    ).all()
    inbound = (
        await session.execute(
            select(AssetRelationship, Asset.display_name)
            .join(Asset, Asset.id == AssetRelationship.from_asset_id)
            .where(AssetRelationship.tenant_id == tenant_id, AssetRelationship.to_asset_id == asset_id)
        )
    ).all()

    owners = (
        await session.execute(
            select(AssetOwner, User.email)
            .join(User, User.id == AssetOwner.user_id)
            .where(AssetOwner.tenant_id == tenant_id, AssetOwner.asset_id == asset_id)
        )
    ).all()

    tags = (
        await session.execute(
            select(AssetTag).where(AssetTag.tenant_id == tenant_id, AssetTag.asset_id == asset_id)
        )
    ).scalars().all()

    return asset, asset_type, outbound, inbound, owners, tags


async def list_asset_changes(
    session: AsyncSession, *, tenant_id: uuid.UUID, asset_id: uuid.UUID
) -> list[AssetChange]:
    result = await session.execute(
        select(AssetChange)
        .where(AssetChange.tenant_id == tenant_id, AssetChange.asset_id == asset_id)
        .order_by(AssetChange.changed_at.desc())
    )
    return list(result.scalars().all())


async def update_criticality(
    session: AsyncSession, *, tenant_id: uuid.UUID, asset_id: uuid.UUID, criticality: str
) -> tuple[Asset, AssetType]:
    row = (
        await session.execute(
            select(Asset, AssetType)
            .join(AssetType, AssetType.id == Asset.asset_type_id)
            .where(Asset.id == asset_id, Asset.tenant_id == tenant_id)
        )
    ).one_or_none()
    if row is None:
        raise NotFoundError("Asset not found.")
    asset, asset_type = row
    if asset.criticality != criticality:
        session.add(
            AssetChange(
                tenant_id=tenant_id,
                asset_id=asset.id,
                field_name="criticality",
                old_value=asset.criticality,
                new_value=criticality,
                changed_at=_now(),
            )
        )
        asset.criticality = criticality
        asset.last_assessed_at = _now()
    await session.flush()
    return asset, asset_type


async def assign_owner(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    asset_id: uuid.UUID,
    user_id: uuid.UUID,
    ownership_type: str,
) -> AssetOwner:
    asset_exists = (
        await session.execute(select(Asset.id).where(Asset.id == asset_id, Asset.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if asset_exists is None:
        raise NotFoundError("Asset not found.")

    existing = (
        await session.execute(
            select(AssetOwner).where(
                AssetOwner.tenant_id == tenant_id,
                AssetOwner.asset_id == asset_id,
                AssetOwner.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.ownership_type = ownership_type
        await session.flush()
        return existing

    owner = AssetOwner(tenant_id=tenant_id, asset_id=asset_id, user_id=user_id, ownership_type=ownership_type)
    session.add(owner)
    await session.flush()
    return owner
