import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.permissions.models import Permission, Role, RolePermission


async def get_permission_keys_for_role(session: AsyncSession, role_id: uuid.UUID) -> set[str]:
    stmt = (
        select(Permission.key)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role_id)
    )
    result = await session.execute(stmt)
    return {row[0] for row in result.all()}


async def get_role_by_tenant_and_name(
    session: AsyncSession, *, tenant_id: uuid.UUID | None, name: str
) -> Role | None:
    stmt = select(Role).where(Role.tenant_id == tenant_id, Role.name == name)
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_roles_for_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> list[Role]:
    stmt = select(Role).where(Role.tenant_id == tenant_id).order_by(Role.name)
    return list((await session.execute(stmt)).scalars().all())


async def get_role_by_id(session: AsyncSession, role_id: uuid.UUID) -> Role | None:
    stmt = select(Role).where(Role.id == role_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_all_permissions(session: AsyncSession) -> list[Permission]:
    return list((await session.execute(select(Permission))).scalars().all())


async def create_role(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID | None,
    name: str,
    description: str,
    is_platform_role: bool,
) -> Role:
    role = Role(
        tenant_id=tenant_id, name=name, description=description, is_platform_role=is_platform_role
    )
    session.add(role)
    await session.flush()
    return role


async def grant_permissions_to_role(
    session: AsyncSession,
    *,
    role_id: uuid.UUID,
    tenant_id: uuid.UUID | None,
    permission_ids: list[uuid.UUID],
) -> None:
    for permission_id in permission_ids:
        session.add(
            RolePermission(tenant_id=tenant_id, role_id=role_id, permission_id=permission_id)
        )
    await session.flush()
