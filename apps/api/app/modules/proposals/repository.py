import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.proposals.models import (
    Proposal,
    ProposalLineItem,
    ProposalTemplate,
    ProposalTemplateLineItem,
)


class ProposalTemplateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, template_id: uuid.UUID) -> ProposalTemplate | None:
        return self.db.execute(
            select(ProposalTemplate).where(ProposalTemplate.tenant_id == tenant_id, ProposalTemplate.id == template_id)
        ).scalar_one_or_none()

    def list_for_tenant(self, tenant_id: uuid.UUID, *, active_only: bool = False) -> list[ProposalTemplate]:
        stmt = select(ProposalTemplate).where(ProposalTemplate.tenant_id == tenant_id)
        if active_only:
            stmt = stmt.where(ProposalTemplate.is_active.is_(True))
        return list(self.db.execute(stmt.order_by(ProposalTemplate.sort_order)).scalars().all())

    def create(
        self, *, tenant_id: uuid.UUID, name: str, description: str = "", terms: str = "", sort_order: int = 0
    ) -> ProposalTemplate:
        template = ProposalTemplate(
            tenant_id=tenant_id, name=name, description=description, terms=terms, sort_order=sort_order
        )
        self.db.add(template)
        self.db.flush()
        return template

    def delete(self, tenant_id: uuid.UUID, template_id: uuid.UUID) -> None:
        template = self.get(tenant_id, template_id)
        if template is not None:
            self.db.delete(template)
            self.db.flush()


class ProposalTemplateLineItemRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_template(self, tenant_id: uuid.UUID, template_id: uuid.UUID) -> list[ProposalTemplateLineItem]:
        return list(
            self.db.execute(
                select(ProposalTemplateLineItem)
                .where(ProposalTemplateLineItem.tenant_id == tenant_id, ProposalTemplateLineItem.template_id == template_id)
                .order_by(ProposalTemplateLineItem.sort_order)
            )
            .scalars()
            .all()
        )

    def replace_for_template(self, tenant_id: uuid.UUID, template_id: uuid.UUID, items: list[dict]) -> list[ProposalTemplateLineItem]:
        existing = self.list_for_template(tenant_id, template_id)
        for row in existing:
            self.db.delete(row)
        self.db.flush()

        created = []
        for index, item in enumerate(items):
            row = ProposalTemplateLineItem(
                tenant_id=tenant_id, template_id=template_id, description=item["description"],
                quantity=item.get("quantity", 1), unit_price=item.get("unit_price", 0), sort_order=index,
            )
            self.db.add(row)
            created.append(row)
        self.db.flush()
        return created


class ProposalRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, proposal_id: uuid.UUID) -> Proposal | None:
        return self.db.execute(
            select(Proposal).where(Proposal.tenant_id == tenant_id, Proposal.id == proposal_id)
        ).scalar_one_or_none()

    def get_by_public_token(self, token: str) -> Proposal | None:
        """Deliberately not tenant-scoped — same reasoning as
        `TenantCaptureTokenRepository.get_by_token`: the token itself is
        the authorization proof for the public acceptance page."""
        return self.db.execute(select(Proposal).where(Proposal.public_token == token)).scalar_one_or_none()

    def list_for_tenant(self, tenant_id: uuid.UUID, *, lead_id: uuid.UUID | None = None) -> list[Proposal]:
        stmt = select(Proposal).where(Proposal.tenant_id == tenant_id)
        if lead_id is not None:
            stmt = stmt.where(Proposal.lead_id == lead_id)
        return list(self.db.execute(stmt.order_by(Proposal.created_at.desc())).scalars().all())

    def create(self, **fields) -> Proposal:
        proposal = Proposal(**fields)
        self.db.add(proposal)
        self.db.flush()
        return proposal


class ProposalLineItemRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_proposal(self, tenant_id: uuid.UUID, proposal_id: uuid.UUID) -> list[ProposalLineItem]:
        return list(
            self.db.execute(
                select(ProposalLineItem)
                .where(ProposalLineItem.tenant_id == tenant_id, ProposalLineItem.proposal_id == proposal_id)
                .order_by(ProposalLineItem.sort_order)
            )
            .scalars()
            .all()
        )

    def replace_for_proposal(self, tenant_id: uuid.UUID, proposal_id: uuid.UUID, items: list[dict]) -> list[ProposalLineItem]:
        existing = self.list_for_proposal(tenant_id, proposal_id)
        for row in existing:
            self.db.delete(row)
        self.db.flush()

        created = []
        for index, item in enumerate(items):
            row = ProposalLineItem(
                tenant_id=tenant_id, proposal_id=proposal_id, description=item["description"],
                quantity=item.get("quantity", 1), unit_price=item.get("unit_price", 0), sort_order=index,
            )
            self.db.add(row)
            created.append(row)
        self.db.flush()
        return created
