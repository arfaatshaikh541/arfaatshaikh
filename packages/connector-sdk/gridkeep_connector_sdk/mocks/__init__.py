from gridkeep_connector_sdk.mocks.backup import MockBackupConnector
from gridkeep_connector_sdk.mocks.cloud import MockCloudConnector
from gridkeep_connector_sdk.mocks.endpoint import MockEndpointConnector
from gridkeep_connector_sdk.mocks.identity import MockIdentityConnector
from gridkeep_connector_sdk.mocks.threat_intel import MockThreatIntelConnector

ALL_MOCK_CONNECTORS = (
    MockIdentityConnector,
    MockEndpointConnector,
    MockCloudConnector,
    MockBackupConnector,
    MockThreatIntelConnector,
)

__all__ = [
    "ALL_MOCK_CONNECTORS",
    "MockBackupConnector",
    "MockCloudConnector",
    "MockEndpointConnector",
    "MockIdentityConnector",
    "MockThreatIntelConnector",
]
