from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.user import User
from app.repositories.membership import MembershipRepository
from app.repositories.tenant import TenantRepository
from app.schemas.lead import LeadAnswerOut, LeadDetailOut
from app.schemas.rbac import RoleOut
from app.schemas.user import CurrentUserOut, MembershipSummary


def build_current_user_out(db: Session, user: User) -> CurrentUserOut:
    memberships = MembershipRepository(db).list_for_user(user.id)
    tenant_repo = TenantRepository(db)
    summaries: list[MembershipSummary] = []
    for membership in memberships:
        tenant = tenant_repo.get_by_id(membership.tenant_id)
        if tenant is None:
            continue
        summaries.append(
            MembershipSummary(
                tenant_id=tenant.id,
                tenant_slug=tenant.slug,
                tenant_name=tenant.name,
                role=RoleOut.model_validate(membership.role),
                status=membership.status,
            )
        )
    return CurrentUserOut(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        is_platform_super_admin=user.is_platform_super_admin,
        email_verified=user.email_verified_at is not None,
        memberships=summaries,
    )


def build_lead_detail_out(lead: Lead) -> LeadDetailOut:
    base = LeadDetailOut.model_validate(lead)
    base.answers = [LeadAnswerOut.model_validate(a) for a in lead.answers]
    base.tag_ids = [link.tag_id for link in lead.tag_links]
    return base
