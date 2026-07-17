"""Role, Permission and RolePermission models.

Roles with tenant_id = NULL are platform roles (Platform Super Admin,
Platform Support Engineer, Platform Operations Manager, Platform Auditor).
Roles with tenant_id set are tenant roles, scoped to that tenant only.

The composite unique constraint (tenant_id, id) on `roles` lets
`memberships` and `role_permissions` declare a composite foreign key
`(tenant_id, role_id) REFERENCES roles(tenant_id, id)`. Because a
membership's tenant_id is always non-null, that composite FK can only ever
be satisfied by a *tenant-scoped* role row - a platform role (tenant_id
NULL) can never be matched, so a tenant membership is structurally
prevented from being assigned a platform role at the database level.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, ForeignKeyConstraint, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPKMixin


class Role(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_roles_tenant_id_id"),
        Index("ix_roles_tenant_name", "tenant_id", "name", unique=True),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_platform_role: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_system_role: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Permission(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "permissions"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)


class RolePermission(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),
        ForeignKeyConstraint(
            ["tenant_id", "role_id"],
            ["roles.tenant_id", "roles.id"],
            name="fk_role_permissions_tenant_role",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class PlatformRoleAssignment(Base, UUIDPKMixin, TimestampMixin):
    """Assigns a platform role (Role.tenant_id IS NULL) to a platform-staff
    user. Deliberately a separate table from `memberships`: memberships are
    always tenant-scoped (tenant_id NOT NULL) and its composite FK to
    `roles(tenant_id, id)` can never match a platform role, so platform
    role assignment needs its own path. A database trigger
    (`enforce_platform_role_assignment`, added in the RLS/hardening
    migration) additionally rejects any row here whose role_id points at a
    tenant-scoped role, so this boundary holds even if application code
    has a bug.
    """

    __tablename__ = "platform_role_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_platform_role_assignments_user_role"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
