"""milestone30 mfa lockout and account recovery

Revision ID: f2c53ba8fbc5
Revises: 636ee68487fe
Create Date: 2026-07-19 08:13:28.490330

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'f2c53ba8fbc5'
down_revision: str | None = '636ee68487fe'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Hardening-programme Milestone 2 (finding H-01): a wrong TOTP/backup-code
# guess against `/api/auth/mfa/verify-login` previously left the challenge
# token usable for the rest of its 10-minute TTL — no attempt counter
# existed anywhere. `failed_attempts` lets the service layer permanently
# invalidate a token after a fixed number of wrong guesses, independent of
# (and a durable backstop to) the new Redis-backed per-token rate limit
# added alongside it in `modules.identity.routes`.
_MFA_MAX_FAILED_ATTEMPTS_DEFAULT = 0

# The self-service MFA-lockout recovery path Milestone 24's backup codes
# don't fully close: a user who has lost their authenticator device AND
# every backup code has no way back in. `account_recovery_requests` mirrors
# `support_access_grants`' second-approver shape (created pending, resolved
# by a genuinely different user) rather than inventing a new pattern. See
# `modules.identity.models.AccountRecoveryRequest` for why this table
# deliberately carries no `tenant_id` column.
_RECOVERY_ENUM_NAME = "account_recovery_status"
_RECOVERY_ENUM_VALUES = ("pending", "approved", "denied")


def upgrade() -> None:
    op.add_column(
        "mfa_challenge_tokens",
        sa.Column(
            "failed_attempts", sa.Integer(), nullable=False, server_default=str(_MFA_MAX_FAILED_ATTEMPTS_DEFAULT)
        ),
    )

    # `create_type=False` on the object used inside the Column below is
    # required — without it, SQLAlchemy tries to CREATE TYPE a second time
    # as part of emitting the CREATE TABLE DDL, since it doesn't know the
    # explicit `.create()` call two lines down already made the type exist.
    recovery_status_enum = postgresql.ENUM(*_RECOVERY_ENUM_VALUES, name=_RECOVERY_ENUM_NAME, create_type=False)
    recovery_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "account_recovery_requests",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("status", recovery_status_enum, nullable=False, server_default="pending"),
        sa.Column("resolved_by_user_id", sa.UUID(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_in_tenant_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_account_recovery_requests_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"],
            ["users.id"],
            name=op.f("fk_account_recovery_requests_resolved_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_in_tenant_id"],
            ["tenants.id"],
            name=op.f("fk_account_recovery_requests_resolved_in_tenant_id_tenants"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_recovery_requests")),
    )
    op.create_index(
        op.f("ix_account_recovery_requests_user_id"), "account_recovery_requests", ["user_id"], unique=False
    )
    # Enforced at the application layer too (recovery_service.request_recovery
    # returns the existing row instead of inserting a second one), but a
    # partial unique index makes "at most one pending request per user" a
    # real database constraint, not just an application convention — the
    # same reasoning `_SIMPLE_TENANT_TABLES`' RLS policies apply to
    # cross-tenant isolation applies here to duplicate-request spam.
    op.create_index(
        "ux_account_recovery_requests_one_pending_per_user",
        "account_recovery_requests",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )

    # No RLS on this table, deliberately — same reasoning as `invitations`
    # (see 762368bc730d): there is no single `tenant_id` to key a policy on,
    # since `User` explicitly supports membership across multiple tenants.
    # Visibility for a reviewing admin is computed at query time by joining
    # to `memberships` for the target user's tenant — see
    # `recovery_service.list_pending_requests_for_tenant` — not enforced by
    # RLS on this table itself.


def downgrade() -> None:
    op.drop_index("ux_account_recovery_requests_one_pending_per_user", table_name="account_recovery_requests")
    op.drop_index(op.f("ix_account_recovery_requests_user_id"), table_name="account_recovery_requests")
    op.drop_table("account_recovery_requests")
    postgresql.ENUM(name=_RECOVERY_ENUM_NAME).drop(op.get_bind())
    op.drop_column("mfa_challenge_tokens", "failed_attempts")
