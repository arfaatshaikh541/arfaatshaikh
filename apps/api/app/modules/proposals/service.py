import uuid
from datetime import UTC, datetime
from datetime import date as date_
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.core.security import generate_opaque_token
from app.modules.proposals.models import Proposal, ProposalStatus
from app.modules.proposals.repository import (
    ProposalLineItemRepository,
    ProposalRepository,
    ProposalTemplateLineItemRepository,
    ProposalTemplateRepository,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


# --- Templates -----------------------------------------------------------

def list_templates(db: Session, tenant_id: uuid.UUID, *, active_only: bool = False):
    return ProposalTemplateRepository(db).list_for_tenant(tenant_id, active_only=active_only)


def get_template_or_404(db: Session, tenant_id: uuid.UUID, template_id: uuid.UUID):
    template = ProposalTemplateRepository(db).get(tenant_id, template_id)
    if template is None:
        raise NotFoundError("Proposal template not found.")
    return template


def create_template(
    db: Session, *, tenant_id: uuid.UUID, name: str, description: str = "", terms: str = "", line_items: list[dict] | None = None
):
    existing = ProposalTemplateRepository(db).list_for_tenant(tenant_id)
    template = ProposalTemplateRepository(db).create(
        tenant_id=tenant_id, name=name, description=description, terms=terms, sort_order=len(existing)
    )
    if line_items:
        ProposalTemplateLineItemRepository(db).replace_for_template(tenant_id, template.id, line_items)
    return template


def update_template_line_items(db: Session, tenant_id: uuid.UUID, template_id: uuid.UUID, *, line_items: list[dict]):
    get_template_or_404(db, tenant_id, template_id)
    return ProposalTemplateLineItemRepository(db).replace_for_template(tenant_id, template_id, line_items)


def list_template_line_items(db: Session, tenant_id: uuid.UUID, template_id: uuid.UUID):
    return ProposalTemplateLineItemRepository(db).list_for_template(tenant_id, template_id)


def delete_template(db: Session, tenant_id: uuid.UUID, template_id: uuid.UUID) -> None:
    ProposalTemplateRepository(db).delete(tenant_id, template_id)


# --- Totals ----------------------------------------------------------------

def compute_totals(line_items: list, *, tax_rate) -> dict:
    """Computed on-the-fly from line items rather than stored as columns,
    to avoid a stored total drifting out of sync with the line items it's
    derived from."""
    subtotal = sum((Decimal(str(item.quantity)) * Decimal(str(item.unit_price)) for item in line_items), Decimal("0"))
    tax_amount = (subtotal * Decimal(str(tax_rate)) / Decimal("100")).quantize(Decimal("0.01"))
    subtotal = subtotal.quantize(Decimal("0.01"))
    total = subtotal + tax_amount
    return {"subtotal": subtotal, "tax_amount": tax_amount, "total": total}


# --- Proposals ---------------------------------------------------------

def list_proposals(db: Session, tenant_id: uuid.UUID, *, lead_id: uuid.UUID | None = None):
    return ProposalRepository(db).list_for_tenant(tenant_id, lead_id=lead_id)


def get_proposal_or_404(db: Session, tenant_id: uuid.UUID, proposal_id: uuid.UUID) -> Proposal:
    proposal = ProposalRepository(db).get(tenant_id, proposal_id)
    if proposal is None:
        raise NotFoundError("Proposal not found.")
    return proposal


def list_line_items(db: Session, tenant_id: uuid.UUID, proposal_id: uuid.UUID):
    return ProposalLineItemRepository(db).list_for_proposal(tenant_id, proposal_id)


def create_proposal(
    db: Session, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, title: str, template_id: uuid.UUID | None = None,
    currency: str = "AED", tax_rate=Decimal("0"), terms: str = "", valid_until: date_ | None = None,
    line_items: list[dict] | None = None, created_by: uuid.UUID | None = None,
) -> Proposal:
    from app.modules.leads.repository import LeadRepository

    lead = LeadRepository(db).get(tenant_id, lead_id)
    if lead is None:
        raise NotFoundError("Lead not found.")

    resolved_terms = terms
    resolved_items = line_items
    if template_id is not None:
        template = get_template_or_404(db, tenant_id, template_id)
        if not resolved_terms:
            resolved_terms = template.terms
        if resolved_items is None:
            template_items = ProposalTemplateLineItemRepository(db).list_for_template(tenant_id, template_id)
            resolved_items = [
                {"description": item.description, "quantity": item.quantity, "unit_price": item.unit_price}
                for item in template_items
            ]

    proposal = ProposalRepository(db).create(
        tenant_id=tenant_id, lead_id=lead_id, template_id=template_id, title=title, currency=currency,
        tax_rate=tax_rate, terms=resolved_terms, valid_until=valid_until, created_by=created_by,
    )
    if resolved_items:
        ProposalLineItemRepository(db).replace_for_proposal(tenant_id, proposal.id, resolved_items)

    from app.modules.audit.service import log_event

    log_event(db, tenant_id=tenant_id, actor_user_id=created_by, action="proposal.created", entity_type="proposal", entity_id=proposal.id)
    return proposal


def update_proposal_line_items(db: Session, tenant_id: uuid.UUID, proposal_id: uuid.UUID, *, line_items: list[dict]):
    proposal = get_proposal_or_404(db, tenant_id, proposal_id)
    if proposal.status != ProposalStatus.DRAFT:
        raise ValidationFailedError("Only draft proposals can be edited.", code="proposal_not_editable")
    return ProposalLineItemRepository(db).replace_for_proposal(tenant_id, proposal_id, line_items)


def _proposal_context(proposal: Proposal, lead, tenant, totals: dict) -> dict:
    return {
        "first_name": lead.first_name if lead else "",
        "last_name": lead.last_name if lead else "",
        "reference_number": lead.reference_number if lead else "",
        "tenant_name": tenant.name if tenant else "",
        "proposal_title": proposal.title,
        "proposal_total": f"{totals['total']} {proposal.currency}",
        "proposal_link": f"/proposals/view/{proposal.public_token}" if proposal.public_token else "",
    }


def send_proposal(db: Session, *, tenant_id: uuid.UUID, proposal: Proposal, actor_id: uuid.UUID | None) -> Proposal:
    if proposal.status not in {ProposalStatus.DRAFT, ProposalStatus.SENT}:
        raise ValidationFailedError("Only a draft proposal can be sent.", code="proposal_not_sendable")

    if not proposal.public_token:
        proposal.public_token = generate_opaque_token(num_bytes=32)
    proposal.status = ProposalStatus.SENT
    proposal.sent_at = _utcnow()
    db.add(proposal)
    db.flush()

    from app.modules.audit.service import log_event
    from app.modules.leads.repository import LeadRepository
    from app.modules.tenancy import service as tenancy_service

    log_event(db, tenant_id=tenant_id, actor_user_id=actor_id, action="proposal.sent", entity_type="proposal", entity_id=proposal.id)

    lead = LeadRepository(db).get(tenant_id, proposal.lead_id)
    if lead is not None:
        from app.modules.crm.service import record_activity

        record_activity(
            db, tenant_id=tenant_id, lead_id=proposal.lead_id, actor_id=actor_id,
            activity_type="proposal.sent", summary=f"Proposal sent: {proposal.title}",
        )

        if lead.email:
            tenant = tenancy_service.get_tenant_or_404(db, tenant_id)
            line_items = list_line_items(db, tenant_id, proposal.id)
            totals = compute_totals(line_items, tax_rate=proposal.tax_rate)
            from app.modules.communications.models import EmailTriggerEvent
            from app.modules.communications.service import send_templated_email

            send_templated_email(
                db, tenant_id=tenant_id, trigger_event=EmailTriggerEvent.PROPOSAL_SENT, recipient=lead.email,
                lead_id=proposal.lead_id, context=_proposal_context(proposal, lead, tenant, totals),
            )
    return proposal


def get_proposal_by_token(db: Session, token: str) -> Proposal:
    """Public, unauthenticated: the token is the authorization proof.
    Establishes RLS context for the resolved tenant before touching any
    other tenant-owned table, same pattern as
    `tenancy.service.resolve_tenant_by_capture_token`."""
    from app.core.db import set_rls_context

    proposal = ProposalRepository(db).get_by_public_token(token)
    if proposal is None:
        raise NotFoundError("Proposal not found.")
    set_rls_context(db, tenant_id=proposal.tenant_id, is_platform_admin=False)

    if proposal.status == ProposalStatus.SENT:
        proposal.viewed_at = proposal.viewed_at or _utcnow()
        proposal.status = ProposalStatus.VIEWED
        db.add(proposal)
        db.flush()
    return proposal


def accept_proposal(db: Session, *, proposal: Proposal, accepted_by_name: str) -> Proposal:
    if proposal.status not in {ProposalStatus.SENT, ProposalStatus.VIEWED}:
        raise ValidationFailedError("This proposal can no longer be accepted.", code="proposal_not_acceptable")
    if proposal.valid_until is not None and date_.today() > proposal.valid_until:
        proposal.status = ProposalStatus.EXPIRED
        db.add(proposal)
        db.flush()
        raise ValidationFailedError("This proposal has expired.", code="proposal_expired")

    proposal.status = ProposalStatus.ACCEPTED
    proposal.accepted_at = _utcnow()
    proposal.accepted_by_name = accepted_by_name
    db.add(proposal)
    db.flush()
    _notify_proposal_outcome(db, proposal=proposal, accepted=True)
    return proposal


def reject_proposal(db: Session, *, proposal: Proposal, rejection_reason: str = "") -> Proposal:
    if proposal.status not in {ProposalStatus.SENT, ProposalStatus.VIEWED}:
        raise ValidationFailedError("This proposal can no longer be rejected.", code="proposal_not_rejectable")

    proposal.status = ProposalStatus.REJECTED
    proposal.rejected_at = _utcnow()
    proposal.rejection_reason = rejection_reason
    db.add(proposal)
    db.flush()
    _notify_proposal_outcome(db, proposal=proposal, accepted=False)
    return proposal


def _notify_proposal_outcome(db: Session, *, proposal: Proposal, accepted: bool) -> None:
    from app.modules.audit.service import log_event
    from app.modules.leads.repository import LeadRepository
    from app.modules.tenancy import service as tenancy_service

    action = "proposal.accepted" if accepted else "proposal.rejected"
    log_event(db, tenant_id=proposal.tenant_id, actor_user_id=None, action=action, entity_type="proposal", entity_id=proposal.id)

    lead = LeadRepository(db).get(proposal.tenant_id, proposal.lead_id)
    if lead is None:
        return

    from app.modules.crm.service import record_activity

    record_activity(
        db, tenant_id=proposal.tenant_id, lead_id=proposal.lead_id, actor_id=None, activity_type=action,
        summary=f"Proposal {'accepted' if accepted else 'rejected'}: {proposal.title}",
    )

    if lead.email:
        tenant = tenancy_service.get_tenant_or_404(db, proposal.tenant_id)
        line_items = list_line_items(db, proposal.tenant_id, proposal.id)
        totals = compute_totals(line_items, tax_rate=proposal.tax_rate)
        from app.modules.communications.models import EmailTriggerEvent
        from app.modules.communications.service import send_templated_email

        send_templated_email(
            db, tenant_id=proposal.tenant_id,
            trigger_event=EmailTriggerEvent.PROPOSAL_ACCEPTED if accepted else EmailTriggerEvent.PROPOSAL_REJECTED,
            recipient=lead.email, lead_id=proposal.lead_id, context=_proposal_context(proposal, lead, tenant, totals),
        )

    from app.modules.workflow_automation.models import WorkflowTriggerEvent
    from app.modules.workflow_automation.service import evaluate_triggers_for_lead

    evaluate_triggers_for_lead(
        db, tenant_id=proposal.tenant_id,
        trigger_event=WorkflowTriggerEvent.PROPOSAL_ACCEPTED if accepted else WorkflowTriggerEvent.PROPOSAL_REJECTED,
        lead=lead, context={"proposal_title": proposal.title},
    )
