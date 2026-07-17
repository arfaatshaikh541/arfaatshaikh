"""BaseConnector: the contract every business-data source connector
implements. Milestone 2 ships `MockConnector` (see mock.py, clearly
labeled fictional data) against this same interface Milestone 3's real
Google Places connector will implement, so campaign orchestration code
never needs to change when a real connector is added."""

from abc import ABC, abstractmethod

from connector_sdk.types import SearchPage, SearchQuery


class BaseConnector(ABC):
    connector_id: str
    source_type: str

    @abstractmethod
    async def estimate_cost(self, query: SearchQuery) -> float:
        """Returns the estimated credit cost of running `query` to
        completion (i.e. across every page up to query.result_limit)."""

    @abstractmethod
    async def search(self, query: SearchQuery) -> SearchPage:
        """Returns one page of results. If `query.cursor` is set, resumes
        from that point; callers page through results by re-invoking this
        with `query.cursor = previous_page.next_cursor` until
        `has_more` is False."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Returns True if the connector is currently able to serve
        requests (reachable, authenticated, within quota)."""
