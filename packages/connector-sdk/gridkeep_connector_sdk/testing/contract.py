"""Shared contract-compliance suite — every connector, mock or real,
is held to the same interface (Rule 9: label simulator vs adapter vs
production, but never let them drift in *behavior*)."""

from __future__ import annotations

from gridkeep_connector_sdk.base import ActionResult, Connector, HealthCheckResult, NormalizedRecord


async def run_connector_contract_checks(connector: Connector) -> list[NormalizedRecord]:
    """Runs a connector through the full contract and returns the records
    it yielded, so callers can layer additional provider-specific
    assertions on top without re-implementing the generic checks."""
    definition = connector.definition
    assert definition.provider_id, "ConnectorDefinition.provider_id must not be empty"
    assert definition.name, "ConnectorDefinition.name must not be empty"
    assert definition.supported_data_types, "A connector must declare at least one supported data type"
    assert definition.sync_modes, "A connector must declare at least one supported sync mode"

    authenticated = await connector.authenticate()
    assert isinstance(authenticated, bool), "authenticate() must return a bool"

    health = await connector.health_check()
    assert isinstance(health, HealthCheckResult), "health_check() must return a HealthCheckResult"

    records: list[NormalizedRecord] = []
    seen_keys: set[tuple[str, str]] = set()
    async for record in connector.sync():
        assert isinstance(record, NormalizedRecord), "sync() must yield NormalizedRecord instances"
        assert record.record_type in definition.supported_data_types, (
            f"record_type '{record.record_type}' is not declared in supported_data_types"
        )
        assert record.identifier_type, "NormalizedRecord.identifier_type must not be empty"
        assert record.identifier_value, "NormalizedRecord.identifier_value must not be empty"
        assert record.external_id, "NormalizedRecord.external_id must not be empty"

        key = (record.identifier_type, record.identifier_value)
        assert key not in seen_keys, f"Duplicate identifier yielded within a single sync: {key}"
        seen_keys.add(key)

        for rel in record.relationships:
            assert rel.relationship_type, "RelationshipRecord.relationship_type must not be empty"
            assert rel.target_identifier_value, "RelationshipRecord.target_identifier_value must not be empty"

        records.append(record)

    await connector.disconnect()  # must not raise

    for action in definition.supported_actions:
        assert action.key, "ActionSpec.key must not be empty"
        assert action.name, "ActionSpec.name must not be empty"
        assert 0 <= action.safety_class <= 4, "ActionSpec.safety_class must be 0-4"
        result = await connector.execute_action(
            action.key, target_identifier_type="test_identifier", target_identifier_value="test-target-1"
        )
        assert isinstance(result, ActionResult), "execute_action() must return an ActionResult"

    return records
