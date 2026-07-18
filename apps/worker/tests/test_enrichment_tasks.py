"""Tests for `worker.enrichment_tasks._run_business_enrichment_async` - the
full enrichment pipeline (crawl -> detect -> persist evidence -> update
Business.email) driven directly against real Postgres, the same approach
`test_campaign_tasks.py` uses for the campaign task chain.

`worker.crawler.fetcher.crawl_site` is monkeypatched to inject an
`httpx.MockTransport` (real internet crawling is not exercised here - see
test_crawler_safety.py's module docstring and docs/adr/0012). The
SSRF-safe resolve-and-validate step inside `safe_get` still runs against
real DNS even through the mock transport, so `example.com` is used as a
website purely as a hostname that genuinely resolves.
"""

import uuid

import httpx
import pytest
from app.modules.businesses import repositories as businesses_repo
from app.modules.enrichment import repositories as enrichment_repo
from app.modules.tenancy import repositories as tenancy_repo
from sqlalchemy.ext.asyncio import async_sessionmaker
from worker import enrichment_tasks as et
from worker.crawler.fetcher import crawl_site as real_crawl_site

pytestmark = pytest.mark.asyncio

ROBOTS_ALLOW_ALL = "User-agent: *\nAllow: /\n"

HOMEPAGE_HTML = """
<html><head><title>Joe's Pizza - Best Pizza in Town</title>
<meta name="description" content="Family owned pizza restaurant since 1990">
<meta name="viewport" content="width=device-width, initial-scale=1">
</head><body>
<footer>Copyright (c) 2019 Joe's Pizza</footer>
<a href="mailto:contact@joespizza.example">Email us</a>
<a href="tel:+15551234567">Call us</a>
<a href="https://facebook.com/joespizza">Facebook</a>
</body></html>
"""

CONTACT_HTML = """
<html><head><title>Contact - Joe's Pizza</title>
<meta name="description" content="Get in touch">
<meta name="viewport" content="width=device-width"></head>
<body>
<form><input name="message"></form>
<a href="mailto:contact@joespizza.example">contact@joespizza.example</a>
</body></html>
"""


def _mock_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/robots.txt":
        return httpx.Response(200, text=ROBOTS_ALLOW_ALL)
    if path == "/":
        return httpx.Response(200, text=HOMEPAGE_HTML)
    if path in ("/contact", "/contact-us"):
        return httpx.Response(200, text=CONTACT_HTML)
    return httpx.Response(404)


def _patch_crawl_site(monkeypatch, handler=_mock_handler):
    async def fake_crawl_site(website_url: str):
        return await real_crawl_site(website_url, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(et, "crawl_site", fake_crawl_site)


async def _make_tenant_and_business(session, *, website: str | None = "https://example.com/"):
    tenant = await tenancy_repo.create_tenant(
        session, name="Enrich Test Co", slug=f"enrich-{uuid.uuid4().hex[:10]}"
    )
    await session.commit()
    business = await businesses_repo.upsert_business_from_discovery(
        session,
        tenant_id=tenant.id,
        campaign_id=None,
        record={
            "source": "mock",
            "source_native_id": f"biz-{uuid.uuid4().hex[:8]}",
            "source_url": "https://example.test/biz-1",
            "collected_at": "2026-01-01T00:00:00+00:00",
            "name": "Joe's Pizza",
            **({"website": website} if website is not None else {}),
        },
    )
    await session.commit()
    return tenant, business


async def _make_enrichment(session, *, tenant_id, business_id):
    enrichment = await enrichment_repo.create_enrichment(
        session, tenant_id=tenant_id, business_id=business_id
    )
    await session.commit()
    return enrichment


async def test_successful_enrichment_persists_evidence_and_sets_email(
    migrator_session, monkeypatch
):
    _patch_crawl_site(monkeypatch)
    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)

    tenant, business = await _make_tenant_and_business(migrator_session)
    enrichment = await _make_enrichment(
        migrator_session, tenant_id=tenant.id, business_id=business.id
    )

    await et._run_business_enrichment_async(str(enrichment.id))

    async with session_factory() as session:
        final_enrichment = await enrichment_repo.get_enrichment_or_raise(session, enrichment.id)
        final_business = await businesses_repo.get_business_or_raise(session, business.id)
        evidence = await enrichment_repo.list_evidence_for_business(session, business.id)

        assert final_enrichment.status == "completed"
        assert final_enrichment.pages_crawled == 3
        assert final_enrichment.error_message is None
        assert final_business.email == "contact@joespizza.example"
        provenance = final_business.field_provenance["email"]
        assert provenance["source"] == "enrichment"
        assert provenance["confidence"] == 0.95

        detector_types = {e.detector_type for e in evidence}
        assert "contact_email" in detector_types
        assert "phone" in detector_types
        assert "social_facebook" in detector_types
        assert "outdated_copyright_year" in detector_types
        # Whole-crawl absence signals fire since nothing on any crawled
        # page matched whatsapp/booking/ordering.
        assert "missing_whatsapp" in detector_types
        assert "missing_online_booking" in detector_types
        assert "missing_online_ordering" in detector_types
        # A contact method (email, phone) WAS found, so this must NOT fire.
        assert "missing_contact_method" not in detector_types
        # The site WAS reachable, so this must NOT fire.
        assert "website_unavailable" not in detector_types

        for e in evidence:
            assert e.enrichment_id == enrichment.id
            assert e.business_id == business.id
            assert e.tenant_id == tenant.id


async def test_business_with_no_website_fails_without_crawling(migrator_session, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not attempt any fetch when there is no website")

    _patch_crawl_site(monkeypatch, handler)
    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)

    tenant, business = await _make_tenant_and_business(migrator_session, website=None)
    enrichment = await _make_enrichment(
        migrator_session, tenant_id=tenant.id, business_id=business.id
    )

    await et._run_business_enrichment_async(str(enrichment.id))

    async with session_factory() as session:
        final_enrichment = await enrichment_repo.get_enrichment_or_raise(session, enrichment.id)
        assert final_enrichment.status == "failed"
        assert final_enrichment.error_message == "Business has no website to crawl."
        evidence = await enrichment_repo.list_evidence_for_business(session, business.id)
        assert evidence == []


async def test_unreachable_site_records_only_website_unavailable(migrator_session, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    _patch_crawl_site(monkeypatch, handler)
    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)

    tenant, business = await _make_tenant_and_business(migrator_session)
    enrichment = await _make_enrichment(
        migrator_session, tenant_id=tenant.id, business_id=business.id
    )

    await et._run_business_enrichment_async(str(enrichment.id))

    async with session_factory() as session:
        final_enrichment = await enrichment_repo.get_enrichment_or_raise(session, enrichment.id)
        final_business = await businesses_repo.get_business_or_raise(session, business.id)
        evidence = await enrichment_repo.list_evidence_for_business(session, business.id)

        assert final_enrichment.status == "completed"
        assert final_enrichment.pages_crawled == 0
        assert final_business.email is None

        detector_types = {e.detector_type for e in evidence}
        assert detector_types == {"website_unavailable"}


async def test_missing_contact_method_fires_when_no_email_or_phone_found(
    migrator_session, monkeypatch
):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS_ALLOW_ALL)
        if path == "/":
            return httpx.Response(
                200,
                text=(
                    "<html><head><title>Joe's Pizza - Home Page</title>"
                    '<meta name="description" content="A restaurant">'
                    '<meta name="viewport" content="width=device-width"></head>'
                    "<body>No contact info at all here.</body></html>"
                ),
            )
        return httpx.Response(404)

    _patch_crawl_site(monkeypatch, handler)
    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)

    tenant, business = await _make_tenant_and_business(migrator_session)
    enrichment = await _make_enrichment(
        migrator_session, tenant_id=tenant.id, business_id=business.id
    )

    await et._run_business_enrichment_async(str(enrichment.id))

    async with session_factory() as session:
        final_business = await businesses_repo.get_business_or_raise(session, business.id)
        evidence = await enrichment_repo.list_evidence_for_business(session, business.id)
        detector_types = {e.detector_type for e in evidence}

        assert final_business.email is None
        assert "missing_contact_method" in detector_types
        assert "contact_email" not in detector_types
        assert "phone" not in detector_types


async def test_duplicate_delivery_of_a_non_pending_enrichment_is_a_noop(
    migrator_session, monkeypatch
):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("a non-pending enrichment must never be re-crawled")

    _patch_crawl_site(monkeypatch, handler)
    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)

    tenant, business = await _make_tenant_and_business(migrator_session)
    enrichment = await _make_enrichment(
        migrator_session, tenant_id=tenant.id, business_id=business.id
    )

    async with session_factory() as session:
        already_running = await enrichment_repo.get_enrichment_or_raise(session, enrichment.id)
        already_running.status = "completed"
        await session.commit()

    # Must return early (no crawl attempted, no exception) since the
    # enrichment is no longer "pending" - simulates a duplicate Celery
    # message delivery for a run another worker already finished.
    await et._run_business_enrichment_async(str(enrichment.id))

    async with session_factory() as session:
        final_enrichment = await enrichment_repo.get_enrichment_or_raise(session, enrichment.id)
        assert final_enrichment.status == "completed"
