"""Tests for `worker.csv_import_tasks._run_csv_import_async` - the CSV
import pipeline end to end: download the uploaded file from object
storage, parse each row through the column mapping, feed it through the
exact same `businesses.repositories.upsert_business_from_discovery` ->
`businesses.dedup.process_new_business_for_duplicates` pipeline a
campaign's discovered businesses already go through, and commit actual
credits used. Same `moto_s3` real-local-S3-server approach
`test_export_tasks.py` uses (see its own module docstring for why).
"""

import uuid
from datetime import UTC, datetime

import pytest
from app.core.storage import upload_bytes
from app.modules.businesses import repositories as businesses_repo
from app.modules.businesses.models import Business
from app.modules.csv_import import repositories as csv_import_repo
from app.modules.csv_import.models import CsvImport
from app.modules.tenancy import repositories as tenancy_repo
from app.modules.usage import repositories as usage_repo
from app.modules.usage.services import grant_credits, reserve_credits
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from worker import csv_import_tasks as ct

pytestmark = pytest.mark.asyncio


async def _make_tenant_with_credits(session, *, balance: float = 100.0):
    tenant = await tenancy_repo.create_tenant(
        session, name="CSV Import Test Co", slug=f"csv-{uuid.uuid4().hex[:10]}"
    )
    await grant_credits(session, tenant_id=tenant.id, amount=balance, type_="grant_purchase")
    return tenant


def _csv_bytes(rows: list[str]) -> bytes:
    return ("\n".join(rows) + "\n").encode("utf-8")


async def _make_queued_import(
    session, *, tenant, file_bytes: bytes, column_mapping: dict, row_count: int
) -> CsvImport:
    object_key = f"tenants/{tenant.id}/csv_imports/{uuid.uuid4()}/import.csv"
    upload_bytes(key=object_key, data=file_bytes, content_type="text/csv")
    csv_import = await csv_import_repo.create_csv_import(
        session,
        tenant_id=tenant.id,
        requested_by_user_id=None,
        object_key=object_key,
        original_filename="import.csv",
        detected_headers=["Business Name", "City", "Phone"],
        sample_rows=[],
        row_count=row_count,
    )
    reservation = await reserve_credits(
        session,
        tenant_id=tenant.id,
        amount=float(row_count),
        reference=f"csv_import:{csv_import.id}",
    )
    await csv_import_repo.mark_queued(
        session, csv_import, column_mapping=column_mapping, reservation_id=reservation.id
    )
    await session.commit()
    return csv_import


async def test_successful_import_creates_businesses_and_commits_actual_credits(
    migrator_session, moto_s3
):
    session = migrator_session
    tenant = await _make_tenant_with_credits(session, balance=100.0)
    file_bytes = _csv_bytes(
        [
            "Business Name,City,Phone",
            "Blue Bottle Cafe,Austin,+1-512-555-0100",
            "Golden Spoon Diner,Austin,+1-512-555-0101",
        ]
    )
    csv_import = await _make_queued_import(
        session,
        tenant=tenant,
        file_bytes=file_bytes,
        column_mapping={"name": "Business Name", "city": "City", "phone": "Phone"},
        row_count=2,
    )

    await ct._run_csv_import_async(str(csv_import.id))

    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)
    async with session_factory() as verify_session:
        refreshed = await csv_import_repo.get_csv_import(verify_session, csv_import.id)
        assert refreshed.status == "completed"
        assert refreshed.imported_count == 2
        assert refreshed.error_count == 0

        wallet = await usage_repo.get_wallet_for_tenant(verify_session, tenant.id)
        # Only the 2 actually-imported rows are debited, not the
        # originally-reserved row_count (which happens to be the same
        # here, but the mechanism - commit_reservation(actual_amount=
        # imported_count) - is what's under test, not the coincidence).
        assert float(wallet.balance) == 100.0 - 2.0


async def test_partial_completion_records_errors_for_rows_missing_name(migrator_session, moto_s3):
    session = migrator_session
    tenant = await _make_tenant_with_credits(session)
    file_bytes = _csv_bytes(
        [
            "Business Name,City,Phone",
            "Real Business Co,Austin,+1-512-555-0100",
            ",Austin,+1-512-555-0199",  # missing required name
        ]
    )
    csv_import = await _make_queued_import(
        session,
        tenant=tenant,
        file_bytes=file_bytes,
        column_mapping={"name": "Business Name", "city": "City", "phone": "Phone"},
        row_count=2,
    )

    await ct._run_csv_import_async(str(csv_import.id))

    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)
    async with session_factory() as verify_session:
        refreshed = await csv_import_repo.get_csv_import(verify_session, csv_import.id)
        assert refreshed.status == "completed"
        assert refreshed.imported_count == 1
        assert refreshed.error_count == 1

        errors = await csv_import_repo.list_errors_for_csv_import(verify_session, csv_import.id)
        assert len(errors) == 1
        assert errors[0].row_number == 2
        assert "name" in errors[0].message.lower()

        wallet = await usage_repo.get_wallet_for_tenant(verify_session, tenant.id)
        assert float(wallet.balance) == 100.0 - 1.0  # only the successful row costs credits


async def test_imported_businesses_are_deduplicated_against_existing_data(
    migrator_session, moto_s3
):
    session = migrator_session
    tenant = await _make_tenant_with_credits(session)
    # A business that already exists (e.g. from a prior campaign) with
    # the exact identifying fields the CSV row below will also carry.
    await businesses_repo.upsert_business_from_discovery(
        session,
        tenant_id=tenant.id,
        campaign_id=None,
        record={
            "source": "mock",
            "source_native_id": "existing-1",
            "source_url": "https://mock-source.example.com/place/existing-1",
            "collected_at": datetime.now(UTC).isoformat(),
            "name": "Silver Fork Bistro",
            "address": "100 Congress Ave",
            "city": "Austin",
            "phone": "+15125550188",
        },
    )
    await session.commit()

    file_bytes = _csv_bytes(
        [
            "Business Name,City,Phone",
            "Silver Fork Bistro,Austin,+1-512-555-0188",
        ]
    )
    csv_import = await _make_queued_import(
        session,
        tenant=tenant,
        file_bytes=file_bytes,
        column_mapping={"name": "Business Name", "city": "City", "phone": "Phone"},
        row_count=1,
    )

    await ct._run_csv_import_async(str(csv_import.id))

    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)
    async with session_factory() as verify_session:
        refreshed = await csv_import_repo.get_csv_import(verify_session, csv_import.id)
        assert refreshed.status == "completed"
        assert refreshed.imported_count == 1

        stmt = select(Business).where(
            Business.tenant_id == tenant.id, Business.merged_into_id.is_(None)
        )
        canonical = (await verify_session.execute(stmt)).scalars().all()
        # The phone-tier exact match auto-merges - only one canonical
        # business survives, proving process_new_business_for_duplicates
        # actually ran against the CSV-imported row.
        assert len(canonical) == 1


async def test_duplicate_delivery_of_a_completed_import_is_a_noop(migrator_session, moto_s3):
    session = migrator_session
    tenant = await _make_tenant_with_credits(session)
    file_bytes = _csv_bytes(["Business Name,City,Phone", "Already Done Co,Austin,+1-512-555-0177"])
    csv_import = await _make_queued_import(
        session,
        tenant=tenant,
        file_bytes=file_bytes,
        column_mapping={"name": "Business Name"},
        row_count=1,
    )
    await ct._run_csv_import_async(str(csv_import.id))

    session_factory = async_sessionmaker(bind=migrator_session.bind, expire_on_commit=False)
    async with session_factory() as verify_session:
        first_pass = await csv_import_repo.get_csv_import(verify_session, csv_import.id)
        assert first_pass.status == "completed"
        wallet_after_first = await usage_repo.get_wallet_for_tenant(verify_session, tenant.id)

    # Re-running a completed import must not re-charge credits or
    # re-process rows - it's a terminal state (unlike "processing",
    # which stays re-enterable for genuine mid-batch retries - see
    # worker.csv_import_tasks's own status-guard comment).
    await ct._run_csv_import_async(str(csv_import.id))

    async with session_factory() as verify_session:
        second_pass = await csv_import_repo.get_csv_import(verify_session, csv_import.id)
        assert second_pass.status == "completed"
        assert second_pass.imported_count == first_pass.imported_count
        wallet_after_second = await usage_repo.get_wallet_for_tenant(verify_session, tenant.id)
        assert float(wallet_after_second.balance) == float(wallet_after_first.balance)
