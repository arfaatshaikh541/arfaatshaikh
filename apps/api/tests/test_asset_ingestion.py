import uuid
from datetime import UTC, datetime

import pytest
from gridkeep_connector_sdk import NormalizedRecord, RelationshipRecord
from sqlalchemy import select

from db.session import set_tenant_context
from modules.assets.ingestion import ingest_sync_records
from modules.assets.models import AssetChange
from modules.integrations import service as integrations_service
from modules.tenancy.models import Tenant, TenantSecurityProfile, TenantSettings

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


async def _make_tenant_integration(
    session, tenant_id: uuid.UUID, provider_id: str = "mock_identity"
) -> uuid.UUID:
    """These ingestion tests exercise the ingestion service in isolation,
    but `assets.tenant_integration_id` is a real FK — a genuine
    TenantIntegration row (via the same connect flow the API uses) keeps
    the test data valid rather than loosening the schema for test
    convenience."""
    tenant_integration = await integrations_service.connect_integration(
        session,
        tenant_id=tenant_id,
        actor_user_id=uuid.uuid4(),
        provider_id=provider_id,
        label="Test Integration",
        secret_plaintext="fake-secret-for-tests",
    )
    await session.flush()
    return tenant_integration.id


def _record(**overrides) -> NormalizedRecord:
    defaults = dict(
        record_type="identity.user",
        external_id="ext-1",
        identifier_type="email",
        identifier_value="user@example.com",
        display_name="Test User",
        attributes={"mfa_enabled": False},
        observed_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return NormalizedRecord(**defaults)


async def test_new_record_creates_one_asset_with_identifier(db):
    tenant_id = await _make_tenant(db, "Ingest New Co")
    integration_id = await _make_tenant_integration(db, tenant_id)

    summary = await ingest_sync_records(
        db, tenant_id=tenant_id, tenant_integration_id=integration_id, provider_id="mock_identity",
        records=[_record()],
    )
    await db.commit()

    assert summary.processed == 1
    assert summary.created == 1
    assert summary.updated == 0


async def test_reingesting_identical_record_is_a_no_op(db):
    tenant_id = await _make_tenant(db, "Ingest Noop Co")
    integration_id = await _make_tenant_integration(db, tenant_id)
    record = _record()

    await ingest_sync_records(
        db, tenant_id=tenant_id, tenant_integration_id=integration_id, provider_id="mock_identity",
        records=[record],
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    summary = await ingest_sync_records(
        db, tenant_id=tenant_id, tenant_integration_id=integration_id, provider_id="mock_identity",
        records=[record],
    )
    await db.commit()

    assert summary.created == 0
    assert summary.updated == 0


async def test_changed_attribute_creates_asset_change_record(db):
    tenant_id = await _make_tenant(db, "Ingest Change Co")
    integration_id = await _make_tenant_integration(db, tenant_id)

    await ingest_sync_records(
        db, tenant_id=tenant_id, tenant_integration_id=integration_id, provider_id="mock_identity",
        records=[_record(attributes={"mfa_enabled": False})],
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    summary = await ingest_sync_records(
        db, tenant_id=tenant_id, tenant_integration_id=integration_id, provider_id="mock_identity",
        records=[_record(attributes={"mfa_enabled": True})],
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    assert summary.created == 0
    assert summary.updated == 1

    changes = (
        await db.execute(select(AssetChange).where(AssetChange.tenant_id == tenant_id))
    ).scalars().all()
    mfa_changes = [c for c in changes if c.field_name == "mfa_enabled"]
    assert len(mfa_changes) == 1
    assert mfa_changes[0].old_value == "false"
    assert mfa_changes[0].new_value == "true"


async def test_two_identifiers_with_same_value_but_different_type_are_distinct_assets(db):
    tenant_id = await _make_tenant(db, "Ingest Distinct Co")
    integration_id = await _make_tenant_integration(db, tenant_id)

    summary = await ingest_sync_records(
        db, tenant_id=tenant_id, tenant_integration_id=integration_id, provider_id="mock_identity",
        records=[
            _record(external_id="a", identifier_type="email", identifier_value="shared-value"),
            _record(external_id="b", identifier_type="hostname", identifier_value="shared-value"),
        ],
    )
    await db.commit()

    assert summary.created == 2


async def test_relationship_resolved_within_same_batch(db):
    tenant_id = await _make_tenant(db, "Ingest Rel Co")
    integration_id = await _make_tenant_integration(db, tenant_id, provider_id="mock_cloud")

    account = _record(
        record_type="cloud.account",
        external_id="acct-1",
        identifier_type="cloud_account_id",
        identifier_value="acct-1",
        display_name="Account 1",
        attributes={},
    )
    resource = _record(
        record_type="cloud.resource",
        external_id="res-1",
        identifier_type="cloud_resource_id",
        identifier_value="res-1",
        display_name="Resource 1",
        attributes={"public_access": True},
        relationships=(
            RelationshipRecord(
                relationship_type="belongs_to",
                target_identifier_type="cloud_account_id",
                target_identifier_value="acct-1",
            ),
        ),
    )

    summary = await ingest_sync_records(
        db, tenant_id=tenant_id, tenant_integration_id=integration_id, provider_id="mock_cloud",
        records=[resource, account],  # resource listed before its target — order must not matter
    )
    await db.commit()

    assert summary.created == 2
    assert summary.relationships_created == 1


async def test_unmapped_record_type_is_skipped_not_errored(db):
    tenant_id = await _make_tenant(db, "Ingest Skip Co")
    integration_id = await _make_tenant_integration(db, tenant_id, provider_id="mock_threat_intel")

    summary = await ingest_sync_records(
        db, tenant_id=tenant_id, tenant_integration_id=integration_id, provider_id="mock_threat_intel",
        records=[
            _record(
                record_type="threat_intel.indicator",
                identifier_type="indicator_value",
                identifier_value="1.2.3.4",
            )
        ],
    )
    await db.commit()

    assert summary.processed == 1
    assert summary.skipped == 1
    assert summary.created == 0
