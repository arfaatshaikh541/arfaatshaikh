import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.db import get_db
from app.dependencies.entitlements import require_module
from app.dependencies.permissions import require_permission
from app.modules.proposals import service as proposals_service
from app.modules.proposals.schemas import (
    AcceptProposalRequest,
    CreateProposalRequest,
    CreateProposalTemplateRequest,
    RejectProposalRequest,
    SetProposalLineItemsRequest,
    SetTemplateLineItemsRequest,
)

public_router = APIRouter(prefix="/public/proposals", tags=["public-proposals"])
templates_router = APIRouter(prefix="/tenant/proposal-templates", tags=["proposal-templates"])
router = APIRouter(prefix="/tenant/proposals", tags=["proposals"])


def _line_item_to_dict(item) -> dict:
    return {
        "id": str(item.id), "description": item.description, "quantity": float(item.quantity), "unit_price": float(item.unit_price),
        "sort_order": item.sort_order,
    }


def _template_to_dict(db: Session, tenant_id: uuid.UUID, template) -> dict:
    items = proposals_service.list_template_line_items(db, tenant_id, template.id)
    return {
        "id": str(template.id), "name": template.name, "description": template.description, "terms": template.terms,
        "is_active": template.is_active, "line_items": [_line_item_to_dict(i) for i in items],
    }


def _proposal_to_dict(db: Session, tenant_id: uuid.UUID, proposal) -> dict:
    items = proposals_service.list_line_items(db, tenant_id, proposal.id)
    totals = proposals_service.compute_totals(items, tax_rate=proposal.tax_rate)
    return {
        "id": str(proposal.id), "lead_id": str(proposal.lead_id), "template_id": str(proposal.template_id) if proposal.template_id else None,
        "title": proposal.title, "status": proposal.status.value, "currency": proposal.currency, "tax_rate": float(proposal.tax_rate),
        "terms": proposal.terms, "valid_until": proposal.valid_until.isoformat() if proposal.valid_until else None,
        "public_token": proposal.public_token, "sent_at": proposal.sent_at.isoformat() if proposal.sent_at else None,
        "viewed_at": proposal.viewed_at.isoformat() if proposal.viewed_at else None,
        "accepted_at": proposal.accepted_at.isoformat() if proposal.accepted_at else None,
        "accepted_by_name": proposal.accepted_by_name,
        "rejected_at": proposal.rejected_at.isoformat() if proposal.rejected_at else None,
        "rejection_reason": proposal.rejection_reason,
        "line_items": [_line_item_to_dict(i) for i in items],
        "subtotal": float(totals["subtotal"]), "tax_amount": float(totals["tax_amount"]), "total": float(totals["total"]),
    }


def _public_proposal_to_dict(db: Session, proposal, *, tenant_name: str) -> dict:
    items = proposals_service.list_line_items(db, proposal.tenant_id, proposal.id)
    totals = proposals_service.compute_totals(items, tax_rate=proposal.tax_rate)
    return {
        "title": proposal.title, "status": proposal.status.value, "currency": proposal.currency, "tax_rate": float(proposal.tax_rate),
        "terms": proposal.terms, "valid_until": proposal.valid_until.isoformat() if proposal.valid_until else None,
        "tenant_name": tenant_name,
        "line_items": [{"description": i.description, "quantity": float(i.quantity), "unit_price": float(i.unit_price)} for i in items],
        "subtotal": float(totals["subtotal"]), "tax_amount": float(totals["tax_amount"]), "total": float(totals["total"]),
    }


# --- Templates -----------------------------------------------------------

@templates_router.get("")
def list_templates(
    ctx: TenantContext = Depends(require_permission("proposals.view")),
    _mod: TenantContext = Depends(require_module("proposals")), db: Session = Depends(get_db),
) -> list[dict]:
    return [_template_to_dict(db, ctx.tenant_id, t) for t in proposals_service.list_templates(db, ctx.tenant_id)]


@templates_router.post("", status_code=201)
def create_template(
    payload: CreateProposalTemplateRequest, ctx: TenantContext = Depends(require_permission("proposals.manage")),
    _mod: TenantContext = Depends(require_module("proposals")), db: Session = Depends(get_db),
) -> dict:
    template = proposals_service.create_template(
        db, tenant_id=ctx.tenant_id, name=payload.name, description=payload.description, terms=payload.terms,
        line_items=[i.model_dump() for i in payload.line_items],
    )
    return _template_to_dict(db, ctx.tenant_id, template)


@templates_router.put("/{template_id}/line-items")
def set_template_line_items(
    template_id: uuid.UUID, payload: SetTemplateLineItemsRequest, ctx: TenantContext = Depends(require_permission("proposals.manage")),
    _mod: TenantContext = Depends(require_module("proposals")), db: Session = Depends(get_db),
) -> dict:
    template = proposals_service.get_template_or_404(db, ctx.tenant_id, template_id)
    proposals_service.update_template_line_items(db, ctx.tenant_id, template_id, line_items=[i.model_dump() for i in payload.line_items])
    return _template_to_dict(db, ctx.tenant_id, template)


@templates_router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("proposals.manage")),
    _mod: TenantContext = Depends(require_module("proposals")), db: Session = Depends(get_db),
) -> None:
    proposals_service.delete_template(db, ctx.tenant_id, template_id)


# --- Proposals --------------------------------------------------------

@router.get("")
def list_proposals(
    lead_id: uuid.UUID | None = None, ctx: TenantContext = Depends(require_permission("proposals.view")),
    _mod: TenantContext = Depends(require_module("proposals")), db: Session = Depends(get_db),
) -> list[dict]:
    return [_proposal_to_dict(db, ctx.tenant_id, p) for p in proposals_service.list_proposals(db, ctx.tenant_id, lead_id=lead_id)]


@router.get("/{proposal_id}")
def get_proposal(
    proposal_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("proposals.view")),
    _mod: TenantContext = Depends(require_module("proposals")), db: Session = Depends(get_db),
) -> dict:
    proposal = proposals_service.get_proposal_or_404(db, ctx.tenant_id, proposal_id)
    return _proposal_to_dict(db, ctx.tenant_id, proposal)


@router.post("", status_code=201)
def create_proposal(
    payload: CreateProposalRequest, ctx: TenantContext = Depends(require_permission("proposals.manage")),
    _mod: TenantContext = Depends(require_module("proposals")), db: Session = Depends(get_db),
) -> dict:
    proposal = proposals_service.create_proposal(
        db, tenant_id=ctx.tenant_id, lead_id=payload.lead_id, title=payload.title, template_id=payload.template_id,
        currency=payload.currency, tax_rate=payload.tax_rate, terms=payload.terms, valid_until=payload.valid_until,
        line_items=[i.model_dump() for i in payload.line_items] if payload.line_items is not None else None,
        created_by=ctx.user_id,
    )
    return _proposal_to_dict(db, ctx.tenant_id, proposal)


@router.put("/{proposal_id}/line-items")
def set_proposal_line_items(
    proposal_id: uuid.UUID, payload: SetProposalLineItemsRequest, ctx: TenantContext = Depends(require_permission("proposals.manage")),
    _mod: TenantContext = Depends(require_module("proposals")), db: Session = Depends(get_db),
) -> dict:
    proposals_service.update_proposal_line_items(db, ctx.tenant_id, proposal_id, line_items=[i.model_dump() for i in payload.line_items])
    proposal = proposals_service.get_proposal_or_404(db, ctx.tenant_id, proposal_id)
    return _proposal_to_dict(db, ctx.tenant_id, proposal)


@router.post("/{proposal_id}/send")
def send_proposal(
    proposal_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("proposals.manage")),
    _mod: TenantContext = Depends(require_module("proposals")), db: Session = Depends(get_db),
) -> dict:
    proposal = proposals_service.get_proposal_or_404(db, ctx.tenant_id, proposal_id)
    proposal = proposals_service.send_proposal(db, tenant_id=ctx.tenant_id, proposal=proposal, actor_id=ctx.user_id)
    return _proposal_to_dict(db, ctx.tenant_id, proposal)


# --- Public acceptance surface -------------------------------------------
# Deliberately NOT gated behind the `proposals` module entitlement: a
# client who already received a proposal must never be blocked from
# viewing/accepting/rejecting it because the tenant's subscription state
# changed after it was sent.

@public_router.get("/{token}")
def public_get_proposal(token: str, db: Session = Depends(get_db)) -> dict:
    from app.modules.tenancy import service as tenancy_service

    proposal = proposals_service.get_proposal_by_token(db, token)
    tenant = tenancy_service.get_tenant_or_404(db, proposal.tenant_id)
    return _public_proposal_to_dict(db, proposal, tenant_name=tenant.name)


@public_router.post("/{token}/accept")
def public_accept_proposal(token: str, payload: AcceptProposalRequest, db: Session = Depends(get_db)) -> dict:
    from app.core.db import set_rls_context

    proposal = proposals_service.get_proposal_by_token(db, token)
    set_rls_context(db, tenant_id=proposal.tenant_id, is_platform_admin=False)
    proposal = proposals_service.accept_proposal(db, proposal=proposal, accepted_by_name=payload.accepted_by_name)
    return {"status": proposal.status.value}


@public_router.post("/{token}/reject")
def public_reject_proposal(token: str, payload: RejectProposalRequest, db: Session = Depends(get_db)) -> dict:
    from app.core.db import set_rls_context

    proposal = proposals_service.get_proposal_by_token(db, token)
    set_rls_context(db, tenant_id=proposal.tenant_id, is_platform_admin=False)
    proposal = proposals_service.reject_proposal(db, proposal=proposal, rejection_reason=payload.rejection_reason)
    return {"status": proposal.status.value}
