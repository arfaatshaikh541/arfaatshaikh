from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.pipeline_stages import DEFAULT_SERVICES
from app.core.security import hash_password
from app.models.tenant import Tenant, TenantSettings
from app.repositories.membership import MembershipRepository
from app.repositories.pipeline import PipelineStageRepository
from app.repositories.role import RoleRepository
from app.repositories.service import ServiceRepository
from app.repositories.tenant import TenantRepository
from app.repositories.user import UserRepository
from app.services.catalog_service import slugify
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.workflow_service import WorkflowService


class TenantService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.tenants = TenantRepository(db)
        self.users = UserRepository(db)
        self.roles = RoleRepository(db)
        self.memberships = MembershipRepository(db)
        self.pipeline_stages = PipelineStageRepository(db)
        self.services_repo = ServiceRepository(db)
        self.workflows = WorkflowService(db)

    def create_tenant_with_owner(
        self,
        *,
        name: str,
        slug: str,
        legal_name: str | None,
        timezone: str,
        currency: str,
        owner_email: str,
        owner_first_name: str,
        owner_last_name: str,
        owner_password: str,
        verify_owner_email: bool = False,
    ) -> Tenant:
        if self.tenants.get_by_slug(slug) is not None:
            raise ConflictError(f"Tenant slug '{slug}' is already in use.")

        tenant = self.tenants.create(
            slug=slug, name=name, legal_name=legal_name, timezone=timezone, currency=currency
        )
        roles = self.roles.create_defaults_for_tenant(tenant.id)
        self.pipeline_stages.create_defaults_for_tenant(tenant.id)
        for index, service_name in enumerate(DEFAULT_SERVICES):
            self.services_repo.create(
                tenant_id=tenant.id, name=service_name, slug=slugify(service_name), sort_order=index
            )
        self.workflows.create_defaults_for_tenant(tenant.id)

        owner = self.users.get_by_email(owner_email)
        if owner is None:
            owner = self.users.create(
                email=owner_email,
                hashed_password=hash_password(owner_password),
                first_name=owner_first_name,
                last_name=owner_last_name,
                email_verified=verify_owner_email,
            )
        elif self.memberships.get_for_user_and_tenant(owner.id, tenant.id) is not None:
            raise ConflictError("This user already belongs to this tenant.")

        self.memberships.create(tenant_id=tenant.id, user_id=owner.id, role_id=roles["owner"].id)
        self.db.flush()
        return tenant

    def get_tenant_or_404(self, tenant_id: uuid.UUID) -> Tenant:
        tenant = self.tenants.get_by_id(tenant_id)
        if tenant is None:
            raise NotFoundError("Tenant not found.")
        return tenant

    def get_settings_or_404(self, tenant_id: uuid.UUID) -> TenantSettings:
        settings = self.tenants.get_settings(tenant_id)
        if settings is None:
            raise NotFoundError("Tenant settings not found.")
        return settings

    def update_profile(self, tenant: Tenant, **fields: object) -> Tenant:
        for key, value in fields.items():
            if value is not None:
                setattr(tenant, key, value)
        self.db.flush()
        return tenant

    def update_settings(self, settings: TenantSettings, **fields: object) -> TenantSettings:
        for key, value in fields.items():
            if value is not None:
                setattr(settings, key, value)
        self.db.flush()
        return settings

    def set_status(self, tenant: Tenant, status: str) -> Tenant:
        if status not in ("active", "suspended", "archived"):
            raise ValidationError("Invalid tenant status.")
        tenant.status = status
        self.db.flush()
        return tenant
