import uuid
from dataclasses import dataclass

from app.modules.tenancy.models import TenantStatus


@dataclass(frozen=True)
class AuthContext:
    """The authenticated principal for the current request, resolved from
    the session cookie. Carries no tenant information — that is resolved
    separately by the tenant-context dependency."""

    user_id: uuid.UUID
    email: str
    is_platform_admin: bool
    session_id: uuid.UUID


@dataclass(frozen=True)
class TenantContext:
    """The tenant the current request is operating against, derived
    exclusively from the authenticated user's session + a live membership
    row — never from a client-supplied tenant_id."""

    tenant_id: uuid.UUID
    tenant_slug: str
    tenant_status: TenantStatus
    membership_id: uuid.UUID
    role_id: uuid.UUID
    role_name: str
    permission_codes: frozenset[str]
    user_id: uuid.UUID
    is_platform_admin: bool

    def has_permission(self, code: str) -> bool:
        return code in self.permission_codes
