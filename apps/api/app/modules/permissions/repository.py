import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.permissions.models import Permission, Role, RolePermission


class PermissionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_code(self, code: str) -> Permission | None:
        return self.db.execute(select(Permission).where(Permission.code == code)).scalar_one_or_none()

    def list_all(self) -> list[Permission]:
        return list(self.db.execute(select(Permission).order_by(Permission.code)).scalars().all())

    def create(self, *, code: str, description: str, is_platform_permission: bool = False) -> Permission:
        permission = Permission(code=code, description=description, is_platform_permission=is_platform_permission)
        self.db.add(permission)
        self.db.flush()
        return permission


class RoleRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, role_id: uuid.UUID) -> Role | None:
        return self.db.get(Role, role_id)

    def get_by_name(self, tenant_id: uuid.UUID | None, name: str) -> Role | None:
        return self.db.execute(
            select(Role).where(Role.tenant_id == tenant_id, Role.name == name)
        ).scalar_one_or_none()

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[Role]:
        return list(self.db.execute(select(Role).where(Role.tenant_id == tenant_id).order_by(Role.name)).scalars().all())

    def create(self, *, tenant_id: uuid.UUID | None, name: str, is_system: bool = False) -> Role:
        role = Role(tenant_id=tenant_id, name=name, is_system=is_system)
        self.db.add(role)
        self.db.flush()
        return role

    def set_permissions(self, role: Role, permission_ids: list[uuid.UUID]) -> None:
        self.db.execute(RolePermission.__table__.delete().where(RolePermission.role_id == role.id))
        for permission_id in permission_ids:
            self.db.add(RolePermission(role_id=role.id, permission_id=permission_id))
        self.db.flush()

    def get_permission_codes(self, role_id: uuid.UUID) -> set[str]:
        rows = self.db.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
        ).scalars().all()
        return set(rows)
