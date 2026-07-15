import pytest

from gridkeep_connector_sdk.mocks import ALL_MOCK_CONNECTORS
from gridkeep_connector_sdk.testing import run_connector_contract_checks


@pytest.mark.parametrize("connector_class", ALL_MOCK_CONNECTORS, ids=lambda c: c.definition.provider_id)
async def test_mock_connector_satisfies_contract(connector_class):
    connector = connector_class(credential_plaintext="fake-test-credential")
    records = await run_connector_contract_checks(connector)
    assert len(records) > 0


@pytest.mark.parametrize("connector_class", ALL_MOCK_CONNECTORS, ids=lambda c: c.definition.provider_id)
def test_mock_connector_is_labelled_simulator(connector_class):
    assert connector_class.definition.is_simulator is True


def test_provider_ids_are_unique():
    provider_ids = [c.definition.provider_id for c in ALL_MOCK_CONNECTORS]
    assert len(provider_ids) == len(set(provider_ids))


async def test_cloud_connector_yields_belongs_to_relationship():
    from gridkeep_connector_sdk.mocks.cloud import MockCloudConnector

    connector = MockCloudConnector(credential_plaintext="fake")
    records = [r async for r in connector.sync()]
    resources = [r for r in records if r.record_type == "cloud.resource"]
    assert resources
    for resource in resources:
        assert any(rel.relationship_type == "belongs_to" for rel in resource.relationships)
