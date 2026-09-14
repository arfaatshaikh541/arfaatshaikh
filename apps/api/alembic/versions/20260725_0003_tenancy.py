"""add organisations, RBAC and audit tables

Revision ID: 20260725_0003
Revises: 20260725_0002
Create Date: 2026-07-25
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20260725_0003"
down_revision: str | None = "20260725_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "organisations",
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("status", sa.String(24), server_default="active", nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organisations")),
        sa.UniqueConstraint("slug", name=op.f("uq_organisations_slug")),
    )
    op.create_index(op.f("ix_organisations_slug"), "organisations", ["slug"], unique=True)

    op.create_table(
        "permissions",
        sa.Column("code", sa.String(120), nullable=False),
        sa.Column("description", sa.String(240), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permissions")),
        sa.UniqueConstraint("code", name=op.f("uq_permissions_code")),
    )
    op.create_index(op.f("ix_permissions_code"), "permissions", ["code"], unique=True)

    op.create_table(
        "roles",
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.String(240), nullable=True),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], name=op.f("fk_roles_organisation_id_organisations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("organisation_id", "name", name="uq_roles_organisation_name"),
        sa.UniqueConstraint("id", "organisation_id", name="uq_roles_id_organisation_id"),
    )
    op.create_index(op.f("ix_roles_organisation_id"), "roles", ["organisation_id"], unique=False)

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("permission_id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], name=op.f("fk_role_permissions_permission_id_permissions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name=op.f("fk_role_permissions_role_id_roles"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role_permissions")),
        sa.UniqueConstraint("role_id", "permission_id", name=op.f("uq_role_permissions_role_id")),
    )
    op.create_index(op.f("ix_role_permissions_role_id"), "role_permissions", ["role_id"], unique=False)
    op.create_index(op.f("ix_role_permissions_permission_id"), "role_permissions", ["permission_id"], unique=False)

    op.create_table(
        "memberships",
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(24), server_default="active", nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], name=op.f("fk_memberships_organisation_id_organisations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id", "organisation_id"], ["roles.id", "roles.organisation_id"], name="fk_memberships_role_organisation", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_memberships_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
        sa.UniqueConstraint("organisation_id", "user_id", name=op.f("uq_memberships_organisation_id")),
    )
    for name, cols in (("ix_memberships_organisation_id", ["organisation_id"]), ("ix_memberships_user_id", ["user_id"]), ("ix_memberships_role_id", ["role_id"]), ("ix_memberships_user_status", ["user_id", "status"])):
        op.create_index(name, "memberships", cols, unique=False)

    op.create_table(
        "platform_administrators",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_platform_administrators_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_administrators")),
        sa.UniqueConstraint("user_id", name=op.f("uq_platform_administrators_user_id")),
    )
    op.create_index(op.f("ix_platform_administrators_user_id"), "platform_administrators", ["user_id"], unique=True)

    op.create_table(
        "support_access_grants",
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("administrator_user_id", sa.Uuid(), nullable=False),
        sa.Column("granted_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["administrator_user_id"], ["users.id"], name=op.f("fk_support_access_grants_administrator_user_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"], name=op.f("fk_support_access_grants_granted_by_user_id_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], name=op.f("fk_support_access_grants_organisation_id_organisations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_support_access_grants")),
    )
    op.create_index(op.f("ix_support_access_grants_organisation_id"), "support_access_grants", ["organisation_id"], unique=False)
    op.create_index(op.f("ix_support_access_grants_administrator_user_id"), "support_access_grants", ["administrator_user_id"], unique=False)
    op.create_index("ix_support_grants_org_expiry", "support_access_grants", ["organisation_id", "expires_at"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("organisation_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("target_type", sa.String(80), nullable=True),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("metadata_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name=op.f("fk_audit_events_actor_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], name=op.f("fk_audit_events_organisation_id_organisations"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    for name, cols in (("ix_audit_events_organisation_id", ["organisation_id"]), ("ix_audit_events_actor_user_id", ["actor_user_id"]), ("ix_audit_events_action", ["action"]), ("ix_audit_events_org_created", ["organisation_id", "created_at"])):
        op.create_index(name, "audit_events", cols, unique=False)

    op.create_table(
        "security_events",
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("organisation_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("metadata_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], name=op.f("fk_security_events_organisation_id_organisations"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_security_events_user_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_security_events")),
    )
    for name, cols in (("ix_security_events_user_id", ["user_id"]), ("ix_security_events_organisation_id", ["organisation_id"]), ("ix_security_events_event_type", ["event_type"]), ("ix_security_events_user_created", ["user_id", "created_at"])):
        op.create_index(name, "security_events", cols, unique=False)


def downgrade() -> None:
    for table in ("security_events", "audit_events", "support_access_grants", "platform_administrators", "memberships", "role_permissions", "roles", "permissions", "organisations"):
        op.drop_table(table)
