"""Tests for `worker.export_tasks._run_export_async` - the export
pipeline end to end: resolve a selection into lead ids, assemble rows
from real Business/LeadScore/LeadOpportunity/LeadRecommendation/
LeadNote/LeadAssignment/BusinessSourceRecord/EnrichmentEvidence data,
build the workbook/CSV, upload it, and mark the `Export` row completed -
then reopen the generated file and validate its actual structure and
content, per the architecture's explicit "workbook validation tests"
requirement. Same "call the private async function directly, bypass the
Celery broker" approach `test_enrichment_tasks.py` already established.

No real MinIO/S3 server is available in this sandbox (no Docker daemon,
no installable MinIO binary - see docs/adr/0015's live-verification
section), so `moto`'s `ThreadedMotoServer` stands in: a genuine local HTTP
server that implements real S3 API semantics, bound to a random port and
pointed at via `S3_ENDPOINT_URL` - `boto3` (via `app.core.storage`)
cannot tell the difference from a real bucket, since it is a real,
un-mocked HTTP round trip against a real (if in-memory) S3 implementation.
"""

import csv
import io
import uuid
from datetime import UTC, datetime

import boto3
import pytest
from app.core.config import get_settings
from app.modules.businesses import repositories as businesses_repo
from app.modules.campaigns import repositories as campaigns_repo
from app.modules.enrichment import repositories as enrichment_repo
from app.modules.exports import repositories as exports_repo
from app.modules.exports.models import Export
from app.modules.identity.models import User
from app.modules.leads import repositories as leads_repo
from app.modules.leads import scoring
from app.modules.tenancy import repositories as tenancy_repo
from moto.server import ThreadedMotoServer
from openpyxl import load_workbook
from sqlalchemy.ext.asyncio import async_sessionmaker
from worker import export_tasks as et

pytestmark = pytest.mark.asyncio


@pytest.fixture
def moto_s3(monkeypatch):
    server = ThreadedMotoServer(port=0, verbose=False)
    server.start()
    host, port = server.get_host_and_port()
    endpoint_url = f"http://{host}:{port}"

    monkeypatch.setenv("S3_ENDPOINT_URL", endpoint_url)
    get_settings.cache_clear()

    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name=get_settings().s3_region,
    )
    client.create_bucket(Bucket=get_settings().s3_bucket_name)

    try:
        yield client
    finally:
        server.stop()
        get_settings.cache_clear()


async def _make_tenant(session):
    return await tenancy_repo.create_tenant(
        session, name="Export Test Co", slug=f"exp-{uuid.uuid4().hex[:10]}"
    )


async def _make_user(session, *, email: str) -> User:
    user = User(email=email, password_hash="x", full_name="Rep One", email_verified=True)
    session.add(user)
    await session.flush()
    return user


async def _make_full_lead(
    session, *, tenant_id, campaign, native_id="=cmd|dangerous", website=True
):
    record = {
        "source": "mock",
        "source_native_id": native_id,
        "source_url": "https://mock-source.example.com/place/1",
        "collected_at": datetime.now(UTC).isoformat(),
        "name": native_id,
        "category": "Restaurant",
        "city": "Springfield",
        "country": "USA",
        "rating": 4.2,
        "review_count": 5,
    }
    if website:
        record["website"] = "https://joespizza.example.com"
    business = await businesses_repo.upsert_business_from_discovery(
        session, tenant_id=tenant_id, campaign_id=campaign.id if campaign else None, record=record
    )

    if website:
        enrichment = await enrichment_repo.create_enrichment(
            session, tenant_id=tenant_id, business_id=business.id
        )
        enrichment.status = "completed"
        await enrichment_repo.record_evidence(
            session,
            tenant_id=tenant_id,
            business_id=business.id,
            enrichment_id=enrichment.id,
            detector_type="social_facebook",
            source_url="https://joespizza.example.com",
            structured_result={"url": "https://facebook.com/joespizza"},
            confidence=0.9,
            collected_at=datetime.now(UTC),
        )

    lead, _score, _o, _r = await scoring.score_lead(session, business.id)
    return lead, business


async def test_xlsx_export_completes_and_workbook_is_valid(migrator_session, moto_s3):
    session = migrator_session
    tenant = await _make_tenant(session)
    user = await _make_user(session, email="rep@example.com")
    campaign = await campaigns_repo.create_campaign(
        session,
        tenant_id=tenant.id,
        name="Spring Push",
        source_key="mock",
        result_limit=10,
        created_by_user_id=user.id,
    )
    lead, business = await _make_full_lead(session, tenant_id=tenant.id, campaign=campaign)
    await leads_repo.create_assignment(
        session,
        tenant_id=tenant.id,
        lead_id=lead.id,
        assigned_to_user_id=user.id,
        assigned_by_user_id=None,
        assigned_at=datetime.now(UTC),
    )
    await leads_repo.create_note(
        session, tenant_id=tenant.id, lead_id=lead.id, author_user_id=user.id, body="Called them."
    )

    export = Export(
        tenant_id=tenant.id,
        requested_by_user_id=user.id,
        format="xlsx",
        status="pending",
        selection={"mode": "lead_ids", "lead_ids": [str(lead.id)]},
    )
    session.add(export)
    await session.flush()
    await session.commit()

    await et._run_export_async(str(export.id))

    # `_run_export_async` writes through its own AsyncSessionLocal
    # sessions, not `migrator_session` - a fresh session (same approach
    # `test_enrichment_tasks.py` uses) is required to see committed
    # changes rather than `migrator_session`'s now-stale identity map.
    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)
    async with session_factory() as verify_session:
        refreshed = await exports_repo.get_export(verify_session, export.id)
        assert refreshed.status == "completed"
        assert refreshed.row_count == 1
        assert refreshed.error_count == 0
        assert refreshed.object_key is not None
        object_key = refreshed.object_key

    settings = get_settings()
    obj = moto_s3.get_object(Bucket=settings.s3_bucket_name, Key=object_key)
    content = obj["Body"].read()

    wb = load_workbook(io.BytesIO(content))
    assert wb.sheetnames == ["Leads", "Campaign Summary", "Scoring Rules", "Errors"]

    leads_ws = wb["Leads"]
    header = [c.value for c in next(leads_ws.iter_rows(min_row=1, max_row=1))]
    assert header[0] == "Business Name"
    assert "Lead Score" in header
    assert "Opening Hours" in header
    assert "Verification Status" in header

    data_row = [c.value for c in next(leads_ws.iter_rows(min_row=2, max_row=2))]
    row = dict(zip(header, data_row, strict=True))
    # Formula-injection protection: a business name starting with "="
    # must never survive as a literal formula-triggering leading char.
    assert row["Business Name"].startswith("'=")
    assert row["Category"] == "Restaurant"
    assert row["City"] == "Springfield"
    assert row["Lead Score"] is not None
    assert row["Assigned User"] == "Rep One"
    assert row["Notes"] and "Called them." in row["Notes"]
    assert row["Facebook URL"] == "https://facebook.com/joespizza"
    # Never fabricated - no data source exists for either column.
    assert row["Opening Hours"] is None
    assert row["Verification Status"] is None

    assert leads_ws.freeze_panes == "A2"
    assert leads_ws.auto_filter.ref is not None

    summary_ws = wb["Campaign Summary"]
    summary_header = [c.value for c in next(summary_ws.iter_rows(min_row=1, max_row=1))]
    assert summary_header == ["Campaign Name", "Status", "Result Limit", "Leads In This Export"]
    summary_row = [c.value for c in next(summary_ws.iter_rows(min_row=2, max_row=2))]
    assert summary_row[0] == "Spring Push"
    assert summary_row[3] == 1

    rules_ws = wb["Scoring Rules"]
    rules_values = [c.value for row in rules_ws.iter_rows(min_row=2) for c in row if c.value]
    assert "No Website" in rules_values or any("Website" in str(v) for v in rules_values)


async def test_csv_export_applies_formula_injection_protection(migrator_session, moto_s3):
    session = migrator_session
    tenant = await _make_tenant(session)
    lead, business = await _make_full_lead(
        session, tenant_id=tenant.id, campaign=None, native_id="=SUM(A1:A2)", website=False
    )

    export = Export(
        tenant_id=tenant.id,
        requested_by_user_id=None,
        format="csv",
        status="pending",
        selection={"mode": "lead_ids", "lead_ids": [str(lead.id)]},
    )
    session.add(export)
    await session.flush()
    await session.commit()

    await et._run_export_async(str(export.id))

    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)
    async with session_factory() as verify_session:
        refreshed = await exports_repo.get_export(verify_session, export.id)
        assert refreshed.status == "completed"
        object_key = refreshed.object_key

    settings = get_settings()
    obj = moto_s3.get_object(Bucket=settings.s3_bucket_name, Key=object_key)
    content = obj["Body"].read()

    text = content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    header = rows[0]
    data = dict(zip(header, rows[1], strict=True))
    assert data["Business Name"].startswith("'=")
    assert data["Category"] == "Restaurant"


async def test_partial_completion_records_export_errors_but_still_completes(
    migrator_session, moto_s3
):
    session = migrator_session
    tenant = await _make_tenant(session)
    lead, business = await _make_full_lead(
        session, tenant_id=tenant.id, campaign=None, native_id="Good Business", website=False
    )
    missing_lead_id = uuid.uuid4()

    export = Export(
        tenant_id=tenant.id,
        requested_by_user_id=None,
        format="csv",
        status="pending",
        selection={"mode": "lead_ids", "lead_ids": [str(lead.id), str(missing_lead_id)]},
    )
    session.add(export)
    await session.flush()
    await session.commit()

    await et._run_export_async(str(export.id))

    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)
    async with session_factory() as verify_session:
        refreshed = await exports_repo.get_export(verify_session, export.id)
        assert refreshed.status == "completed"
        assert refreshed.row_count == 1
        assert refreshed.error_count == 1

        errors = await exports_repo.list_errors_for_export(verify_session, export.id)
        assert len(errors) == 1
        assert errors[0].lead_id == missing_lead_id


async def test_duplicate_delivery_of_a_non_pending_export_is_a_noop(migrator_session, moto_s3):
    session = migrator_session
    tenant = await _make_tenant(session)
    lead, business = await _make_full_lead(
        session, tenant_id=tenant.id, campaign=None, native_id="Already Done Co", website=False
    )

    export = Export(
        tenant_id=tenant.id,
        requested_by_user_id=None,
        format="csv",
        status="completed",
        selection={"mode": "lead_ids", "lead_ids": [str(lead.id)]},
        object_key="tenants/x/exports/x/export.csv",
        row_count=1,
    )
    session.add(export)
    await session.flush()
    await session.commit()

    # The moto_s3 fixture's bucket has no such key - if the task tried to
    # actually re-process this export, the download/upload path would
    # fail; reaching the end without error proves the "already handled"
    # short-circuit fired instead.
    await et._run_export_async(str(export.id))

    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)
    async with session_factory() as verify_session:
        refreshed = await exports_repo.get_export(verify_session, export.id)
        assert refreshed.status == "completed"
        assert refreshed.object_key == "tenants/x/exports/x/export.csv"
