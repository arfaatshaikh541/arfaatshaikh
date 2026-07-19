"""Unit tests for `FaultInjectingConnector` itself - the test-only
connector `apps/worker/tests/test_campaign_task_retry_loop.py` uses to
drive `worker.campaign_tasks.run_campaign_task`'s retry loop end-to-end
with controlled, deterministic connector failures.
"""

import pytest
from connector_sdk.errors import ConnectorAuthError, ConnectorTransientError
from connector_sdk.fault_injecting import FaultInjectingConnector
from connector_sdk.types import SearchQuery

pytestmark = pytest.mark.asyncio


def _query() -> SearchQuery:
    return SearchQuery(industry="Restaurants", country="UAE", city="Dubai", result_limit=5)


async def test_raises_the_scripted_exception_for_each_indexed_call():
    connector = FaultInjectingConnector(
        [ConnectorTransientError("first"), None, ConnectorAuthError("third")]
    )

    with pytest.raises(ConnectorTransientError, match="first"):
        await connector.search(_query())

    page = await connector.search(_query())  # None -> delegates to MockConnector
    assert page.businesses is not None

    with pytest.raises(ConnectorAuthError, match="third"):
        await connector.search(_query())

    assert connector.call_count == 3


async def test_delegates_to_mock_connector_once_outcomes_are_exhausted():
    connector = FaultInjectingConnector([ConnectorTransientError("only the first call fails")])

    with pytest.raises(ConnectorTransientError):
        await connector.search(_query())

    # No more scripted outcomes - every further call succeeds via MockConnector.
    for _ in range(3):
        page = await connector.search(_query())
        assert page.businesses is not None

    assert connector.call_count == 4


async def test_empty_outcomes_always_delegates():
    connector = FaultInjectingConnector([])
    page = await connector.search(_query())
    assert page.businesses is not None
    assert connector.call_count == 1


async def test_estimate_cost_and_health_check_delegate_to_mock_connector():
    connector = FaultInjectingConnector([ConnectorTransientError("search-only failure")])
    assert await connector.estimate_cost(_query()) == 5.0
    assert await connector.health_check() is True
