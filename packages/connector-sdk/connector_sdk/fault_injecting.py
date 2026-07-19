"""FAULT-INJECTING CONNECTOR - test-only, deterministic failure scripting
for exercising a caller's retry/backoff/permanent-failure handling.

Deliberately NOT exported from `connector_sdk/__init__.py` and NOT
registered in `connector_sdk.registry` - it must never be selectable as a
real campaign's `source_key` the way `mock`/`google_places` are. Tests
that need it import it directly
(`from connector_sdk.fault_injecting import FaultInjectingConnector`) and
wire it in by monkeypatching the caller's own `get_connector` reference,
never by touching the production registry.

Closes the "no connector-error-path test coverage through the worker's
own retry loop" gap named since Milestone 3 - `worker.campaign_tasks`'s
retry/backoff/permanent-failure handling had never been driven end-to-end
with a real, controlled sequence of connector failures, only with
`MockConnector`'s always-succeeds behavior.
"""

from collections.abc import Sequence

from connector_sdk.base import BaseConnector
from connector_sdk.mock import MockConnector
from connector_sdk.types import SearchPage, SearchQuery


class FaultInjectingConnector(BaseConnector):
    connector_id = "fault_injecting_test_only"
    source_type = "test_fault_injection"

    def __init__(self, outcomes: Sequence[Exception | None]):
        """`outcomes[i]` applies to the i-th call (0-indexed) to
        `search()`: `None` delegates to a real `MockConnector` call and
        returns its page; an exception instance is raised instead. Once
        `outcomes` is exhausted, every further call delegates to
        `MockConnector` - so a test only needs to script the failures it
        cares about, not every subsequent call."""
        self._outcomes = list(outcomes)
        self._delegate = MockConnector()
        self.call_count = 0

    async def estimate_cost(self, query: SearchQuery) -> float:
        return await self._delegate.estimate_cost(query)

    async def health_check(self) -> bool:
        return await self._delegate.health_check()

    async def search(self, query: SearchQuery) -> SearchPage:
        index = self.call_count
        self.call_count += 1
        outcome = self._outcomes[index] if index < len(self._outcomes) else None
        if outcome is not None:
            raise outcome
        return await self._delegate.search(query)
