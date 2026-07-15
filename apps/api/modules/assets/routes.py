from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import TenantContext, get_tenant_db, require_csrf, require_permission, require_tenant_write
from modules.assets import service as assets_service
from modules.assets.schemas import (
    AssetChangeRead,
    AssetCriticalityUpdate,
    AssetDetail,
    AssetIdentifierRead,
    AssetListItem,
    AssetOwnerAssignRequest,
    AssetOwnerRead,
    AssetRelationshipRead,
)
from modules.audit import service as audit_service

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("", response_model=list[AssetListItem])
async def list_assets(
    asset_type: str | None = Query(default=None),
    criticality: str | None = Query(default=None),
    search: str | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("assets.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[AssetListItem]:
    rows = await assets_service.list_assets(
        db, tenant_id=ctx.tenant_id, asset_type_key=asset_type, criticality=criticality, search=search
    )
    return [
        AssetListItem(
            id=asset.id,
            asset_type=asset_type_row.key,
            display_name=asset.display_name,
            source=asset.source,
            criticality=asset.criticality,
            exposure=asset.exposure,
            lifecycle_status=asset.lifecycle_status,
            last_observed_at=asset.last_observed_at,
        )
        for asset, asset_type_row in rows
    ]


@router.get("/{asset_id}", response_model=AssetDetail)
async def get_asset(
    asset_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("assets.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> AssetDetail:
    asset, asset_type, outbound, inbound, owners, tags = await assets_service.get_asset_detail(
        db, tenant_id=ctx.tenant_id, asset_id=asset_id
    )
    relationships = [
        AssetRelationshipRead(
            relationship_type=rel.relationship_type,
            direction="outbound",
            related_asset_id=rel.to_asset_id,
            related_asset_display_name=name,
            source=rel.source,
            observed_at=rel.observed_at,
        )
        for rel, name in outbound
    ] + [
        AssetRelationshipRead(
            relationship_type=rel.relationship_type,
            direction="inbound",
            related_asset_id=rel.from_asset_id,
            related_asset_display_name=name,
            source=rel.source,
            observed_at=rel.observed_at,
        )
        for rel, name in inbound
    ]
    return AssetDetail(
        id=asset.id,
        asset_type=asset_type.key,
        display_name=asset.display_name,
        source=asset.source,
        confidence=asset.confidence,
        criticality=asset.criticality,
        exposure=asset.exposure,
        lifecycle_status=asset.lifecycle_status,
        attributes=asset.attributes,
        last_observed_at=asset.last_observed_at,
        last_assessed_at=asset.last_assessed_at,
        identifiers=[
            AssetIdentifierRead(identifier_type=i.identifier_type, identifier_value=i.identifier_value)
            for i in asset.identifiers
        ],
        relationships=relationships,
        owners=[
            AssetOwnerRead(user_id=owner.user_id, email=email, ownership_type=owner.ownership_type)
            for owner, email in owners
        ],
        tags={tag.key: tag.value for tag in tags},
    )


@router.get("/{asset_id}/changes", response_model=list[AssetChangeRead])
async def get_asset_changes(
    asset_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("assets.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[AssetChangeRead]:
    changes = await assets_service.list_asset_changes(db, tenant_id=ctx.tenant_id, asset_id=asset_id)
    return [
        AssetChangeRead(
            field_name=c.field_name, old_value=c.old_value, new_value=c.new_value, changed_at=c.changed_at
        )
        for c in changes
    ]


@router.patch("/{asset_id}/criticality", response_model=AssetListItem, dependencies=[Depends(require_csrf)])
async def update_asset_criticality(
    asset_id: uuid.UUID,
    payload: AssetCriticalityUpdate,
    ctx: TenantContext = Depends(require_permission("assets.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> AssetListItem:
    require_tenant_write(ctx)
    asset, asset_type = await assets_service.update_criticality(
        db, tenant_id=ctx.tenant_id, asset_id=asset_id, criticality=payload.criticality
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="assets.criticality_updated",
        target_type="asset",
        target_id=str(asset.id),
        context={"criticality": payload.criticality},
    )
    response = AssetListItem(
        id=asset.id,
        asset_type=asset_type.key,
        display_name=asset.display_name,
        source=asset.source,
        criticality=asset.criticality,
        exposure=asset.exposure,
        lifecycle_status=asset.lifecycle_status,
        last_observed_at=asset.last_observed_at,
    )
    await db.commit()
    return response


@router.post("/{asset_id}/owners", dependencies=[Depends(require_csrf)])
async def assign_asset_owner(
    asset_id: uuid.UUID,
    payload: AssetOwnerAssignRequest,
    ctx: TenantContext = Depends(require_permission("assets.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    require_tenant_write(ctx)
    await assets_service.assign_owner(
        db,
        tenant_id=ctx.tenant_id,
        asset_id=asset_id,
        user_id=payload.user_id,
        ownership_type=payload.ownership_type,
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="assets.owner_assigned",
        target_type="asset",
        target_id=str(asset_id),
        context={"owner_user_id": str(payload.user_id)},
    )
    await db.commit()
    return {"status": "ok"}
