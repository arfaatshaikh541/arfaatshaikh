import re
import uuid

from sqlalchemy.orm import Session

from app.core.db import set_rls_context
from app.core.errors import ConflictError, NotFoundError
from app.modules.tenancy.models import Tenant, TenantCaptureToken, TenantSettings, TenantStatus
from app.modules.tenancy.repository import TenantCaptureTokenRepository, TenantRepository

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "tenant"


def get_tenant(db: Session, tenant_id: uuid.UUID) -> Tenant | None:
    return TenantRepository(db).get(tenant_id)


def get_tenant_or_404(db: Session, tenant_id: uuid.UUID) -> Tenant:
    tenant = get_tenant(db, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found.")
    return tenant


def get_tenant_settings(db: Session, tenant_id: uuid.UUID) -> TenantSettings | None:
    return TenantRepository(db).get_settings(tenant_id)


def update_tenant_settings(db: Session, *, tenant_id: uuid.UUID, updates: dict) -> TenantSettings:
    settings = get_tenant_settings(db, tenant_id)
    if settings is None:
        raise NotFoundError("Tenant settings not found.")
    for field, value in updates.items():
        if value is not None:
            setattr(settings, field, value)
    db.add(settings)
    db.flush()
    return settings


def list_tenants(db: Session, *, limit: int = 200, offset: int = 0) -> list[Tenant]:
    return TenantRepository(db).list_all(limit=limit, offset=offset)


def create_tenant(db: Session, *, name: str, slug: str | None = None) -> Tenant:
    repo = TenantRepository(db)
    candidate_slug = slug or slugify(name)
    if not _SLUG_RE.match(candidate_slug):
        raise ConflictError("Slug must be lowercase alphanumeric with single hyphens.", code="invalid_slug")
    if repo.get_by_slug(candidate_slug):
        raise ConflictError(f"A tenant with slug '{candidate_slug}' already exists.", code="slug_taken")
    return repo.create(name=name, slug=candidate_slug)


def set_tenant_status(db: Session, *, tenant: Tenant, status: TenantStatus) -> Tenant:
    tenant.status = status
    db.add(tenant)
    db.flush()
    return tenant


def get_capture_token(db: Session, tenant_id: uuid.UUID) -> TenantCaptureToken | None:
    return TenantCaptureTokenRepository(db).get_for_tenant(tenant_id)


def resolve_tenant_by_capture_token(db: Session, token: str) -> Tenant | None:
    """Public, unauthenticated lookup — the token itself is the
    authorization proof. Returns None (never raises) for an unknown or
    inactive token so the public capture endpoint can respond with a
    generic 404 rather than distinguishing "wrong token" from "tenant
    archived" etc."""
    capture_token = TenantCaptureTokenRepository(db).get_by_token(token)
    if capture_token is None:
        return None
    # The capture token itself (looked up above with no RLS restriction,
    # same reasoning as invitations/sessions) is the authorization proof
    # for this specific tenant — establish that as the RLS context before
    # reading the (RLS-protected) tenants row, exactly as
    # `identity_service.accept_invitation` does for its own token.
    set_rls_context(db, tenant_id=capture_token.tenant_id, is_platform_admin=False)
    tenant = get_tenant(db, capture_token.tenant_id)
    if tenant is None or tenant.status in {TenantStatus.SUSPENDED, TenantStatus.ARCHIVED}:
        return None
    return tenant


# Statuses under which write operations are rejected platform-wide,
# independent of any module/feature entitlement.
WRITE_BLOCKING_STATUSES = {TenantStatus.SUSPENDED, TenantStatus.READ_ONLY, TenantStatus.ARCHIVED}
READ_BLOCKING_STATUSES = {TenantStatus.SUSPENDED, TenantStatus.ARCHIVED}
