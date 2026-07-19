"""Drives the real Celery-wrapped `worker.enrichment_tasks.run_business_
enrichment` end-to-end through a genuine retry, the same investigation
that found and fixed the equivalent bug in `worker.campaign_tasks` (see
docs/adr/0023): `_run_business_enrichment_async` commits `enrichment.
status = "running"` *before* the crawl step, and nothing ever reset it
back on a retryable failure - `if enrichment.status != "pending": return`
would make a genuine retried delivery silently no-op instead of
re-attempting the crawl.

Plain (non-`async def`) test functions for the same reason `test_campaign_
task_retry_loop.py` uses them: `run_business_enrichment` drives real work
through `run_db_task`, which wraps `asyncio.run(...)` - illegal nested
inside pytest-asyncio's own running loop. Also requests `real_celery_
task_isolation` (conftest.py) for the same reason that file does - see
its own module docstring and the fixture's docstring for the full
cross-event-loop mechanism this works around.
"""

import asyncio
import uuid

import httpx
from celery.exceptions import Retry
from worker import enrichment_tasks as et
from worker.crawler.fetcher import crawl_site as real_crawl_site

ROBOTS_ALLOW_ALL = "User-agent: *\nAllow: /\n"
HOMEPAGE_HTML = """
<html><head><title>Joe's Pizza - Best Pizza in Town</title>
<meta name="description" content="Family owned pizza restaurant since 1990">
<meta name="viewport" content="width=device-width, initial-scale=1">
</head><body>
<footer>Copyright (c) 2019 Joe's Pizza</footer>
<a href="mailto:contact@joespizza.example">Email us</a>
</body></html>
"""


def _mock_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/robots.txt":
        return httpx.Response(200, text=ROBOTS_ALLOW_ALL)
    if path == "/":
        return httpx.Response(200, text=HOMEPAGE_HTML)
    return httpx.Response(404)


def _session_factory():
    from app.core.config import get_settings
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    url = get_settings().database_url_sync.replace("postgresql+psycopg", "postgresql+asyncpg")
    engine = create_async_engine(url)
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False)


async def _setup_tenant_business_and_enrichment():
    from app.modules.businesses import repositories as businesses_repo
    from app.modules.enrichment import repositories as enrichment_repo
    from app.modules.tenancy import repositories as tenancy_repo

    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await tenancy_repo.create_tenant(
                session, name="Enrich Retry Loop Co", slug=f"erl-{uuid.uuid4().hex[:10]}"
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
                    "website": "https://example.com/",
                },
            )
            await session.commit()
            enrichment = await enrichment_repo.create_enrichment(
                session, tenant_id=tenant.id, business_id=business.id
            )
            await session.commit()
            return enrichment.id
    finally:
        await engine.dispose()


async def _get_enrichment_status(enrichment_id) -> str:
    from app.modules.enrichment import repositories as enrichment_repo

    engine, Session = _session_factory()
    try:
        async with Session() as session:
            enrichment = await enrichment_repo.get_enrichment(session, enrichment_id)
            return enrichment.status
    finally:
        await engine.dispose()


def test_transient_crawl_error_retries_then_succeeds(monkeypatch, real_celery_task_isolation):
    enrichment_id = asyncio.run(_setup_tenant_business_and_enrichment())

    call_count = {"n": 0}

    async def fake_crawl_site(website_url: str):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated transient crawl failure")
        return await real_crawl_site(website_url, transport=httpx.MockTransport(_mock_handler))

    monkeypatch.setattr(et, "crawl_site", fake_crawl_site)

    task = et.run_business_enrichment
    task.push_request(called_directly=False, retries=0)
    try:
        raised = False
        try:
            task(str(enrichment_id))
        except Retry:
            raised = True
        assert raised, "expected a Retry exception on the first (transient-failure) attempt"
    finally:
        task.pop_request()

    # If this is "running" instead of "pending", the real retried
    # delivery below will no-op instead of re-attempting the crawl.
    assert asyncio.run(_get_enrichment_status(enrichment_id)) == "pending"

    task.push_request(called_directly=False, retries=1)
    try:
        task(str(enrichment_id))
    finally:
        task.pop_request()

    assert call_count["n"] == 2  # the retry genuinely re-invoked crawl_site
    assert asyncio.run(_get_enrichment_status(enrichment_id)) == "completed"
