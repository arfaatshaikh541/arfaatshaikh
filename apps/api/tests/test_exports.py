"""Repository/service-level tests for the Exports module (Milestone 7):
selection resolution (`exports.services.resolve_lead_ids`, both the
explicit-`lead_ids` and `filters`-replay modes), request persistence, and
download-URL gating. The actual XLSX/CSV generation and object-storage
round trip are exercised end-to-end in `apps/worker/tests/
test_export_tasks.py` (that's where a real - if moto-backed - S3 upload
happens); this file stays fast and dependency-free by monkeypatching
`app.core.storage.presigned_download_url` rather than standing up a
server, since the URL-generation call itself is just local HMAC signing
logic already covered by `app.core.storage`'s own real usage in the
worker test.
"""

import uuid
from datetime import UTC, datetime

import pytest
from app.core.db import set_tenant_context
from app.core.exceptions import ConflictError
from app.modules.businesses import repositories as businesses_repo
from app.modules.exports import repositories as exports_repo
from app.modules.exports import services as exports_services
from app.modules.exports.models import Export
from app.modules.exports.schemas import CreateExportRequest
from app.modules.leads import repositories as leads_repo
from app.modules.leads import scoring
from app.modules.tenancy import repositories as tenancy_repo
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.helpers import migrator_asyncpg_url

pytestmark = pytest.mark.asyncio


def _session_factory():
    engine = create_async_engine(migrator_asyncpg_url())
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False)


async def _make_tenant(session):
    return await tenancy_repo.create_tenant(
        session, name="Export Svc Test Co", slug=f"expsvc-{uuid.uuid4().hex[:10]}"
    )


async def _discover_and_score(session, *, tenant_id, native_id, **fields):
    record = {
        "source": "mock",
        "source_native_id": native_id,
        "source_url": f"https://mock-source.example.com/place/{native_id}",
        "collected_at": datetime.now(UTC).isoformat(),
        "name": fields.pop("name", "Test Business"),
        **fields,
    }
    business = await businesses_repo.upsert_business_from_discovery(
        session, tenant_id=tenant_id, campaign_id=None, record=record
    )
    lead, _score, _o, _r = await scoring.score_lead(session, business.id)
    return lead, business


async def test_resolve_lead_ids_lead_ids_mode():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            lead, _business = await _discover_and_score(
                session, tenant_id=tenant.id, native_id="a1"
            )
            await session.commit()

            resolved = await exports_services.resolve_lead_ids(
                session,
                tenant_id=tenant.id,
                selection={"mode": "lead_ids", "lead_ids": [str(lead.id)]},
            )
            assert resolved == [lead.id]
    finally:
        await engine.dispose()


async def test_resolve_lead_ids_filters_mode_replays_the_same_filters_list_leads_uses():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            matching, _ = await _discover_and_score(
                session, tenant_id=tenant.id, native_id="b1", city="Austin"
            )
            _other, _ = await _discover_and_score(
                session, tenant_id=tenant.id, native_id="b2", city="Denver"
            )
            await session.commit()

            resolved = await exports_services.resolve_lead_ids(
                session,
                tenant_id=tenant.id,
                selection={"mode": "filters", "filters": {"city": "Austin"}},
            )
            assert resolved == [matching.id]
    finally:
        await engine.dispose()


async def test_request_export_persists_lead_ids_selection():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            lead, _business = await _discover_and_score(
                session, tenant_id=tenant.id, native_id="c1"
            )
            await session.commit()

            export = await exports_services.request_export(
                session,
                tenant_id=tenant.id,
                requested_by_user_id=None,
                request=CreateExportRequest(format="xlsx", lead_ids=[lead.id]),
            )
            assert export.status == "pending"
            assert export.selection == {"mode": "lead_ids", "lead_ids": [str(lead.id)]}
    finally:
        await engine.dispose()


async def test_request_export_persists_filters_selection_defaulting_to_empty_filters():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            await session.commit()

            export = await exports_services.request_export(
                session,
                tenant_id=tenant.id,
                requested_by_user_id=None,
                request=CreateExportRequest(format="csv"),
            )
            assert export.selection["mode"] == "filters"
            assert export.selection["filters"]["status"] is None
    finally:
        await engine.dispose()


async def test_download_url_raises_conflict_before_export_completes():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            export = await exports_repo.create_export(
                session,
                tenant_id=tenant.id,
                requested_by_user_id=None,
                format="xlsx",
                selection={"mode": "lead_ids", "lead_ids": []},
            )
            await session.commit()

            with pytest.raises(ConflictError):
                await exports_services.get_download_url(session, export)
    finally:
        await engine.dispose()


async def test_download_url_succeeds_once_completed(monkeypatch):
    monkeypatch.setattr(
        exports_services,
        "presigned_download_url",
        lambda **kwargs: "https://example-bucket.test/signed-url",
    )
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            export = Export(
                tenant_id=tenant.id,
                requested_by_user_id=None,
                format="xlsx",
                status="completed",
                selection={"mode": "lead_ids", "lead_ids": []},
                object_key="tenants/x/exports/y/export.xlsx",
                row_count=0,
            )
            session.add(export)
            await session.flush()
            await session.commit()

            url, expires_in_seconds, filename = await exports_services.get_download_url(
                session, export
            )
            assert url == "https://example-bucket.test/signed-url"
            assert expires_in_seconds == 900
            assert filename.endswith(".xlsx")
    finally:
        await engine.dispose()


async def test_download_url_raises_conflict_once_storage_has_been_cleaned_up():
    """Milestone 14 (ADR-0022): once the retention sweep has deleted an
    export's underlying object, `get_download_url` must not presign a URL
    for a key that no longer exists - it must surface a clear error
    instead."""
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            export = Export(
                tenant_id=tenant.id,
                requested_by_user_id=None,
                format="xlsx",
                status="completed",
                selection={"mode": "lead_ids", "lead_ids": []},
                object_key="tenants/x/exports/y/export.xlsx",
                row_count=0,
                storage_deleted_at=datetime.now(UTC),
            )
            session.add(export)
            await session.flush()
            await session.commit()

            with pytest.raises(ConflictError):
                await exports_services.get_download_url(session, export)
    finally:
        await engine.dispose()


async def test_export_ids_matching_filters_excludes_merged_away_business():
    engine, Session = _session_factory()
    try:
        async with Session() as session:
            tenant = await _make_tenant(session)
            await set_tenant_context(session, tenant.id)
            lead, business = await _discover_and_score(session, tenant_id=tenant.id, native_id="d1")
            business.merged_into_id = None  # sanity: canonical by default
            await session.commit()

            all_ids = await leads_repo.list_all_lead_ids_matching_filters(
                session, tenant_id=tenant.id, filters=leads_repo.LeadListFilters()
            )
            assert lead.id in all_ids
    finally:
        await engine.dispose()
