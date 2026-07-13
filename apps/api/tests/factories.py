"""Test factories. Use the service layer directly (not HTTP) so tests
build fixture state quickly and independently of the API surface."""

from __future__ import annotations

import itertools
import uuid

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.membership import Membership
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.membership import MembershipRepository
from app.repositories.role import RoleRepository
from app.services.tenant_service import TenantService

_counter = itertools.count()

DEFAULT_PASSWORD = "TestPassw0rd!123"


def unique_slug(prefix: str = "tenant") -> str:
    return f"{prefix}-{next(_counter)}-{uuid.uuid4().hex[:6]}"


def make_tenant_with_owner(
    db: Session, *, slug: str | None = None, owner_email: str | None = None
) -> tuple[Tenant, User]:
    slug = slug or unique_slug()
    owner_email = owner_email or f"owner-{uuid.uuid4().hex[:8]}@factory.testmail.dev"
    service = TenantService(db)
    tenant = service.create_tenant_with_owner(
        name=f"Test Co {slug}",
        slug=slug,
        legal_name=None,
        timezone="Asia/Dubai",
        currency="AED",
        owner_email=owner_email,
        owner_first_name="Test",
        owner_last_name="Owner",
        owner_password=DEFAULT_PASSWORD,
        verify_owner_email=True,
    )
    db.commit()
    owner = db.query(User).filter_by(email=owner_email.lower()).one()
    return tenant, owner


def add_member(
    db: Session, tenant: Tenant, *, role_slug: str, email: str | None = None
) -> tuple[User, Membership]:
    from app.repositories.user import UserRepository

    email = email or f"member-{uuid.uuid4().hex[:8]}@factory.testmail.dev"
    user = UserRepository(db).create(
        email=email,
        hashed_password=hash_password(DEFAULT_PASSWORD),
        first_name="Test",
        last_name="Member",
        email_verified=True,
    )
    role = RoleRepository(db).get_by_slug_for_tenant(tenant.id, role_slug)
    assert role is not None, f"role {role_slug} not seeded for tenant"
    membership = MembershipRepository(db).create(
        tenant_id=tenant.id, user_id=user.id, role_id=role.id
    )
    db.commit()
    return user, membership


def login(client, email: str, password: str = DEFAULT_PASSWORD) -> str:
    """Logs in via the real HTTP endpoint (cookies persist on the client) and
    returns the CSRF token to attach to subsequent mutating requests."""
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return client.cookies.get("csrf_token")
