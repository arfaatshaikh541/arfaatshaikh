import re
import uuid

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.modules.tenancy.models import Tenant, TenantSettings, TenantStatus
from app.modules.tenancy.repository import TenantRepository

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


# Statuses under which write operations are rejected platform-wide,
# independent of any module/feature entitlement.
WRITE_BLOCKING_STATUSES = {TenantStatus.SUSPENDED, TenantStatus.READ_ONLY, TenantStatus.ARCHIVED}
READ_BLOCKING_STATUSES = {TenantStatus.SUSPENDED, TenantStatus.ARCHIVED}
