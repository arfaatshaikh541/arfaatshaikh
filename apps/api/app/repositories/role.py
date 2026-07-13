import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import PERMISSIONS
from app.core.roles import DEFAULT_ROLES
from app.models.rbac import Permission, Role


class RoleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def sync_permission_catalog(self) -> dict[str, Permission]:
        """Idempotently ensure every permission in the code catalog exists as a row."""
        existing = {p.code: p for p in self.db.execute(select(Permission)).scalars().all()}
        for definition in PERMISSIONS:
            if definition.code not in existing:
                perm = Permission(code=definition.code, description=definition.description)
                self.db.add(perm)
                existing[definition.code] = perm
        self.db.flush()
        return existing

    def create_defaults_for_tenant(self, tenant_id: uuid.UUID) -> dict[str, Role]:
        permissions_by_code = self.sync_permission_catalog()
        roles: dict[str, Role] = {}
        for default_role in DEFAULT_ROLES:
            role = Role(
                tenant_id=tenant_id,
                name=default_role.name,
                slug=default_role.slug,
                is_system=True,
            )
            role.permissions = [
                permissions_by_code[code]
                for code in default_role.permissions
                if code in permissions_by_code
            ]
            self.db.add(role)
            roles[default_role.slug] = role
        self.db.flush()
        return roles

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[Role]:
        stmt = select(Role).where(Role.tenant_id == tenant_id).order_by(Role.created_at)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id_for_tenant(self, tenant_id: uuid.UUID, role_id: uuid.UUID) -> Role | None:
        stmt = select(Role).where(Role.tenant_id == tenant_id, Role.id == role_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_slug_for_tenant(self, tenant_id: uuid.UUID, slug: str) -> Role | None:
        stmt = select(Role).where(Role.tenant_id == tenant_id, Role.slug == slug)
        return self.db.execute(stmt).scalar_one_or_none()

    def create(
        self, *, tenant_id: uuid.UUID, name: str, slug: str, permission_codes: list[str]
    ) -> Role:
        permissions_by_code = self.sync_permission_catalog()
        role = Role(tenant_id=tenant_id, name=name, slug=slug, is_system=False)
        role.permissions = [
            permissions_by_code[code] for code in permission_codes if code in permissions_by_code
        ]
        self.db.add(role)
        self.db.flush()
        return role

    def update_permissions(self, role: Role, permission_codes: list[str]) -> Role:
        permissions_by_code = self.sync_permission_catalog()
        role.permissions = [
            permissions_by_code[code] for code in permission_codes if code in permissions_by_code
        ]
        self.db.flush()
        return role
