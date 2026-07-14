import uuid

from sqlalchemy.orm import Session

from app.modules.audit.service import log_event
from app.modules.entitlements import service as entitlements_service
from app.modules.identity import service as identity_service
from app.modules.identity.models import MembershipStatus
from app.modules.identity.repository import MembershipRepository
from app.modules.permissions import service as permissions_service
from app.modules.subscriptions import service as subscriptions_service
from app.modules.subscriptions.models import SubscriptionStatus
from app.modules.tenancy import service as tenancy_service
from app.modules.tenancy.models import Tenant


def create_tenant_with_owner(
    db: Session, *, name: str, slug: str | None, plan_code: str, owner_email: str,
    owner_first_name: str, owner_last_name: str, created_by: uuid.UUID,
) -> Tenant:
    """The full platform-admin "create tenant" workflow: tenant + default
    roles + owner account + Tenant Owner membership + initial subscription,
    all in one DB transaction so a failure partway through leaves nothing
    behind."""
    tenant = tenancy_service.create_tenant(db, name=name, slug=slug)

    roles_by_name = permissions_service.provision_default_roles_for_tenant(db, tenant.id)
    owner_role = roles_by_name["Tenant Owner"]

    owner = identity_service.provision_tenant_owner(
        db, email=owner_email, first_name=owner_first_name, last_name=owner_last_name, tenant_name=tenant.name
    )
    MembershipRepository(db).create(
        tenant_id=tenant.id, user_id=owner.id, role_id=owner_role.id, status=MembershipStatus.ACTIVE
    )
    entitlements_service.increment_usage_unchecked(db, tenant.id, metric_code="users", amount=1)

    subscriptions_service.assign_plan(
        db, tenant_id=tenant.id, plan_code=plan_code, changed_by=created_by, status=SubscriptionStatus.ACTIVE
    )

    log_event(
        db, tenant_id=tenant.id, actor_user_id=created_by, action="tenant.created",
        entity_type="tenant", entity_id=tenant.id, after={"name": name, "slug": tenant.slug, "plan_code": plan_code},
    )
    return tenant
