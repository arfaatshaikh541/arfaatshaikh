import uuid

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.modules.permissions.catalog import DEFAULT_TENANT_ROLES, TENANT_PERMISSIONS
from app.modules.permissions.models import Role
from app.modules.permissions.repository import PermissionRepository, RoleRepository


def get_role(db: Session, role_id: uuid.UUID) -> Role | None:
    return RoleRepository(db).get(role_id)


def get_role_permission_codes(db: Session, role_id: uuid.UUID) -> set[str]:
    return RoleRepository(db).get_permission_codes(role_id)


def list_tenant_roles(db: Session, tenant_id: uuid.UUID) -> list[Role]:
    return RoleRepository(db).list_for_tenant(tenant_id)


def create_tenant_role(db: Session, *, tenant_id: uuid.UUID, name: str, permission_codes: list[str]) -> Role:
    role_repo = RoleRepository(db)
    permission_repo = PermissionRepository(db)

    if role_repo.get_by_name(tenant_id, name):
        raise ConflictError(f"A role named '{name}' already exists for this tenant.", code="role_name_taken")

    invalid_codes = set(permission_codes) - set(TENANT_PERMISSIONS.keys())
    if invalid_codes:
        raise ForbiddenError(
            "Cannot assign platform-only or unknown permissions to a tenant role: "
            f"{', '.join(sorted(invalid_codes))}",
            code="platform_permission_not_assignable",
        )

    role = role_repo.create(tenant_id=tenant_id, name=name, is_system=False)
    permission_ids = []
    for code in permission_codes:
        permission = permission_repo.get_by_code(code)
        if permission is None:
            raise NotFoundError(f"Unknown permission code '{code}'.")
        permission_ids.append(permission.id)
    role_repo.set_permissions(role, permission_ids)
    return role


def update_tenant_role_permissions(db: Session, *, tenant_id: uuid.UUID, role_id: uuid.UUID, permission_codes: list[str]) -> Role:
    role_repo = RoleRepository(db)
    permission_repo = PermissionRepository(db)

    role = role_repo.get(role_id)
    if role is None or role.tenant_id != tenant_id:
        raise NotFoundError("Role not found.")
    if role.is_system:
        raise ForbiddenError("System roles cannot be modified.", code="system_role_immutable")

    invalid_codes = set(permission_codes) - set(TENANT_PERMISSIONS.keys())
    if invalid_codes:
        raise ForbiddenError(
            "Cannot assign platform-only or unknown permissions to a tenant role: "
            f"{', '.join(sorted(invalid_codes))}",
            code="platform_permission_not_assignable",
        )

    permission_ids = []
    for code in permission_codes:
        permission = permission_repo.get_by_code(code)
        if permission is None:
            raise NotFoundError(f"Unknown permission code '{code}'.")
        permission_ids.append(permission.id)
    role_repo.set_permissions(role, permission_ids)
    return role


def list_assignable_tenant_permissions() -> dict[str, str]:
    """The only permission catalog a tenant admin may choose from — platform
    permissions are never included, so they are structurally unreachable
    through tenant role management."""
    return dict(TENANT_PERMISSIONS)


def provision_default_roles_for_tenant(db: Session, tenant_id: uuid.UUID) -> dict[str, Role]:
    """Instantiates a concrete, tenant-scoped copy of every default role
    template (Tenant Owner, Administrator, Manager, Sales Agent, Support
    Agent, Viewer) for a newly created tenant. Memberships always
    reference one of these concrete rows, never the NULL-tenant template,
    so editing one tenant's "Manager" role can never affect another
    tenant's."""
    role_repo = RoleRepository(db)
    permission_repo = PermissionRepository(db)
    created: dict[str, Role] = {}
    for role_name, permission_codes in DEFAULT_TENANT_ROLES.items():
        role = role_repo.create(tenant_id=tenant_id, name=role_name, is_system=True)
        permission_ids = []
        for code in permission_codes:
            permission = permission_repo.get_by_code(code)
            if permission is not None:
                permission_ids.append(permission.id)
        role_repo.set_permissions(role, permission_ids)
        created[role_name] = role
    return created
