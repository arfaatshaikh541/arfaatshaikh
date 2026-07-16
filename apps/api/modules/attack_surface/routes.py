from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import TenantContext, get_tenant_db, require_csrf, require_permission, require_tenant_write
from modules.attack_surface import service as attack_surface_service
from modules.attack_surface.schemas import AddDomainRequest, DomainRead, VerifyDomainResult
from modules.attack_surface.service import verification_file_url
from modules.audit import service as audit_service
from modules.tenancy.models import TenantDomain

router = APIRouter(prefix="/api/attack-surface", tags=["attack-surface"])


def _to_domain_read(domain: TenantDomain) -> DomainRead:
    return DomainRead(
        id=domain.id,
        domain=domain.domain,
        is_verified=domain.is_verified,
        verification_method=domain.verification_method,
        verification_token=domain.verification_token,
        verification_file_url=verification_file_url(domain.domain),
        verified_at=domain.verified_at,
        created_at=domain.created_at,
    )


@router.get("/domains", response_model=list[DomainRead])
async def list_domains(
    ctx: TenantContext = Depends(require_permission("assets.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[DomainRead]:
    domains = await attack_surface_service.list_domains(db, tenant_id=ctx.tenant_id)
    return [_to_domain_read(domain) for domain in domains]


@router.post("/domains", response_model=DomainRead, dependencies=[Depends(require_csrf)])
async def add_domain(
    payload: AddDomainRequest,
    ctx: TenantContext = Depends(require_permission("assets.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> DomainRead:
    require_tenant_write(ctx)
    domain = await attack_surface_service.add_domain(db, tenant_id=ctx.tenant_id, domain=payload.domain)
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="attack_surface.domain_added",
        target_type="tenant_domain",
        target_id=str(domain.id),
        context={"domain": domain.domain},
    )
    response = _to_domain_read(domain)
    await db.commit()
    return response


@router.post(
    "/domains/{domain_id}/verify", response_model=VerifyDomainResult, dependencies=[Depends(require_csrf)]
)
async def verify_domain(
    domain_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("assets.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> VerifyDomainResult:
    require_tenant_write(ctx)
    domain, verified_now, message = await attack_surface_service.verify_domain(
        db, tenant_id=ctx.tenant_id, domain_id=domain_id
    )
    if verified_now:
        await audit_service.record(
            db,
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.user.id,
            actor_label=ctx.user.email,
            action="attack_surface.domain_verified",
            target_type="tenant_domain",
            target_id=str(domain.id),
            context={"domain": domain.domain},
        )
    response = VerifyDomainResult(domain=_to_domain_read(domain), verified_now=verified_now, message=message)
    await db.commit()
    return response


@router.delete("/domains/{domain_id}", dependencies=[Depends(require_csrf)])
async def remove_domain(
    domain_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("assets.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    require_tenant_write(ctx)
    domain = await attack_surface_service.get_domain_or_404(db, tenant_id=ctx.tenant_id, domain_id=domain_id)
    await attack_surface_service.remove_domain(db, tenant_id=ctx.tenant_id, domain_id=domain_id)
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="attack_surface.domain_removed",
        target_type="tenant_domain",
        target_id=str(domain_id),
        context={"domain": domain.domain},
    )
    await db.commit()
    return {"status": "ok"}
