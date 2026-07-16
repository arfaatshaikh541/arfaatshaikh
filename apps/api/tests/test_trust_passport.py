import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

import main as app_main
from core.errors import NotFoundError
from db.session import set_tenant_context
from modules.compliance import service as compliance_service
from modules.compliance.models import ComplianceControl, ComplianceFramework
from modules.identity.models import User
from modules.tenancy.models import Tenant, TenantSecurityProfile, TenantSettings
from modules.trust_passport import service as trust_passport_service
from tests.helpers import invite_and_accept_member, login, onboard_verified_owner

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _make_tenant(session, name: str) -> uuid.UUID:
    tenant_id = uuid.uuid4()
    await set_tenant_context(session, tenant_id)
    slug = f"{name.lower().replace(' ', '-')}-{tenant_id.hex[:6]}"
    session.add(Tenant(id=tenant_id, name=name, slug=slug, status="active"))
    await session.flush()
    session.add(TenantSettings(tenant_id=tenant_id, display_name=name))
    session.add(TenantSecurityProfile(tenant_id=tenant_id))
    await session.flush()
    return tenant_id


async def _make_user(session, email: str) -> uuid.UUID:
    user = User(email=email, password_hash="not-a-real-hash", full_name="Test User", email_verified=True)
    session.add(user)
    await session.flush()
    return user.id


async def test_get_settings_defaults_to_none_when_unconfigured(db):
    tenant_id = await _make_tenant(db, "Passport Unconfigured Co")

    settings = await trust_passport_service.get_settings(db, tenant_id=tenant_id)

    assert settings is None


async def test_update_settings_generates_slug_on_first_publish(db):
    tenant_id = await _make_tenant(db, "Passport Publish Co")
    actor_id = await _make_user(db, "actor@passport-publish.example")

    settings = await trust_passport_service.update_settings(
        db, tenant_id=tenant_id, is_published=True, headline="We take security seriously",
        description="Our program at a glance.", show_compliance_frameworks=True, actor_user_id=actor_id,
    )

    assert settings.is_published is True
    assert settings.public_slug is not None
    assert len(settings.public_slug) > 10


async def test_update_settings_does_not_regenerate_slug_on_subsequent_updates(db):
    tenant_id = await _make_tenant(db, "Passport Stable Slug Co")
    actor_id = await _make_user(db, "actor@passport-stable.example")

    first = await trust_passport_service.update_settings(
        db, tenant_id=tenant_id, is_published=True, headline="v1", description="",
        show_compliance_frameworks=True, actor_user_id=actor_id,
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)
    first_slug = first.public_slug

    second = await trust_passport_service.update_settings(
        db, tenant_id=tenant_id, is_published=True, headline="v2", description="",
        show_compliance_frameworks=True, actor_user_id=actor_id,
    )

    assert second.public_slug == first_slug
    assert second.headline == "v2"


async def test_unpublishing_keeps_the_slug_but_hides_the_page(db):
    tenant_id = await _make_tenant(db, "Passport Unpublish Co")
    actor_id = await _make_user(db, "actor@passport-unpublish.example")

    settings = await trust_passport_service.update_settings(
        db, tenant_id=tenant_id, is_published=True, headline="", description="",
        show_compliance_frameworks=True, actor_user_id=actor_id,
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)
    slug = settings.public_slug

    await trust_passport_service.update_settings(
        db, tenant_id=tenant_id, is_published=False, headline="", description="",
        show_compliance_frameworks=True, actor_user_id=actor_id,
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    settings_after = await trust_passport_service.get_settings(db, tenant_id=tenant_id)
    assert settings_after.public_slug == slug  # kept, so republishing reuses the same URL

    with pytest.raises(NotFoundError):
        await trust_passport_service.get_public_passport(db, slug=slug)


async def test_regenerate_slug_changes_it_and_invalidates_the_old_one(db):
    tenant_id = await _make_tenant(db, "Passport Regenerate Co")
    actor_id = await _make_user(db, "actor@passport-regenerate.example")

    settings = await trust_passport_service.update_settings(
        db, tenant_id=tenant_id, is_published=True, headline="", description="",
        show_compliance_frameworks=False, actor_user_id=actor_id,
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)
    old_slug = settings.public_slug

    updated = await trust_passport_service.regenerate_slug(db, tenant_id=tenant_id, actor_user_id=actor_id)
    await db.commit()
    await set_tenant_context(db, tenant_id)

    assert updated.public_slug != old_slug
    with pytest.raises(NotFoundError):
        await trust_passport_service.get_public_passport(db, slug=old_slug)
    passport = await trust_passport_service.get_public_passport(db, slug=updated.public_slug)
    assert passport["headline"] == ""


async def test_regenerate_slug_without_existing_settings_raises_not_found(db):
    tenant_id = await _make_tenant(db, "Passport Regenerate Missing Co")
    actor_id = await _make_user(db, "actor@passport-regenerate-missing.example")

    with pytest.raises(NotFoundError):
        await trust_passport_service.regenerate_slug(db, tenant_id=tenant_id, actor_user_id=actor_id)


async def test_get_public_passport_wrong_slug_raises_not_found(db):
    with pytest.raises(NotFoundError):
        await trust_passport_service.get_public_passport(db, slug="this-slug-does-not-exist")


async def test_public_passport_shows_coarse_labels_not_raw_scores(db):
    tenant_id = await _make_tenant(db, "Passport Labels Co")
    actor_id = await _make_user(db, "actor@passport-labels.example")

    framework = (
        await db.execute(select(ComplianceFramework).where(ComplianceFramework.key == "soc2_type2"))
    ).scalar_one()
    controls = (
        await db.execute(
            select(ComplianceControl)
            .where(ComplianceControl.framework_id == framework.id)
            .order_by(ComplianceControl.sort_order)
        )
    ).scalars().all()
    for control in controls:
        await compliance_service.update_control_status(
            db, tenant_id=tenant_id, control_id=control.id, status="met", note=None, actor_user_id=actor_id,
        )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    settings = await trust_passport_service.update_settings(
        db, tenant_id=tenant_id, is_published=True, headline="Our security posture", description="",
        show_compliance_frameworks=True, actor_user_id=actor_id,
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    passport = await trust_passport_service.get_public_passport(db, slug=settings.public_slug)

    assert passport["compliance_frameworks"] is not None
    soc2_entry = next(f for f in passport["compliance_frameworks"] if f["name"] == "SOC 2 Type II")
    assert soc2_entry["status_label"] == "Strong"
    assert "score" not in soc2_entry
    assert set(soc2_entry.keys()) == {"name", "status_label"}


async def test_public_passport_respects_show_compliance_frameworks_toggle(db):
    tenant_id = await _make_tenant(db, "Passport Toggle Co")
    actor_id = await _make_user(db, "actor@passport-toggle.example")

    settings = await trust_passport_service.update_settings(
        db, tenant_id=tenant_id, is_published=True, headline="", description="",
        show_compliance_frameworks=False, actor_user_id=actor_id,
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    passport = await trust_passport_service.get_public_passport(db, slug=settings.public_slug)

    assert passport["compliance_frameworks"] is None


async def _connected_owner(client, db, *, org: str, email: str, password: str = "Owner-Pass1!"):
    await onboard_verified_owner(client, db, org_name=org, full_name="Owner", email=email, password=password)
    resp = await login(client, email, password)
    assert resp.status_code == 200
    body = resp.json()
    return {
        "tenant_id": body["memberships"][0]["tenant_id"],
        "csrf_token": body["csrf_token"],
        "user_id": body["user"]["id"],
    }


async def test_security_analyst_cannot_manage_trust_passport(client, db):
    ctx = await _connected_owner(
        client, db, org="API Passport Perm Co", email="owner@api-passport-perm.example"
    )
    member = await invite_and_accept_member(
        client, db, tenant_id=ctx["tenant_id"], inviter_csrf_token=ctx["csrf_token"],
        email="analyst@api-passport-perm.example", full_name="Analyst", password="Analyst-Pass1!",
        role_name="security_analyst",
    )

    resp = await client.patch(
        "/api/trust-passport/settings",
        json={"is_published": True, "headline": "x", "description": "", "show_compliance_frameworks": True},
        headers={"X-CSRF-Token": member["csrf_token"]},
    )

    assert resp.status_code == 403


async def test_publish_via_api_and_fetch_public_passport_anonymously(client, db):
    ctx = await _connected_owner(
        client, db, org="API Passport Publish Co", email="owner@api-passport-publish.example"
    )

    settings_resp = await client.get("/api/trust-passport/settings")
    assert settings_resp.status_code == 200
    assert settings_resp.json()["public_slug"] is None

    publish_resp = await client.patch(
        "/api/trust-passport/settings",
        json={
            "is_published": True, "headline": "API Passport Publish Co is secure",
            "description": "See our program.", "show_compliance_frameworks": True,
        },
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert publish_resp.status_code == 200
    slug = publish_resp.json()["public_slug"]
    assert slug is not None

    # A brand-new client with no cookies at all - true anonymous access.
    transport = ASGITransport(app=app_main.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as anon_client:
        public_resp = await anon_client.get(f"/api/public/trust-passport/{slug}")

    assert public_resp.status_code == 200
    body = public_resp.json()
    assert body["headline"] == "API Passport Publish Co is secure"
    assert body["compliance_frameworks"] is not None


async def test_public_passport_404_for_unpublished_slug(client, db):
    await _connected_owner(
        client, db, org="API Passport Draft Co", email="owner@api-passport-draft.example"
    )

    resp = await client.get("/api/public/trust-passport/some-random-nonexistent-slug")

    assert resp.status_code == 404
