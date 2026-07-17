"""MOCK CONNECTOR - clearly fictional data, for local development,
demos, and Milestone 2 testing of the campaign engine only. It performs
no network calls and must never be presented to a user as real business
data; every generated business name is templated from obviously synthetic
word lists and every `source` field is `"mock"`.

Generation is deterministic (seeded from the query + page number) so the
same query always produces the same page, which is what makes retries
and idempotency testable without real-world flakiness.
"""

import hashlib
import random
from datetime import UTC, datetime

from connector_sdk.base import BaseConnector
from connector_sdk.types import BusinessRecord, SearchPage, SearchQuery

_ADJECTIVES = [
    "Golden",
    "Blue",
    "Sunset",
    "Royal",
    "Silver",
    "Northern",
    "Coastal",
    "Urban",
    "Grand",
    "Bright",
]
_SUFFIXES = [
    "House",
    "Corner",
    "Studio",
    "Hub",
    "Collective",
    "Co.",
    "Works",
    "Lounge",
    "Place",
    "Spot",
]


def _seed_for(query: SearchQuery, page_number: int) -> int:
    key = (
        f"{query.industry}|{query.category}|{query.country}|{query.city}|{query.area}|{page_number}"
    )
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)


class MockConnector(BaseConnector):
    connector_id = "mock"
    source_type = "mock_fictional_data"

    async def estimate_cost(self, query: SearchQuery) -> float:
        # 1 credit per requested result is the Milestone 2 pricing model;
        # a real connector's estimate additionally accounts for Place
        # Details calls, pagination overhead, etc. (Milestone 3).
        return float(query.result_limit)

    async def health_check(self) -> bool:
        return True

    async def search(self, query: SearchQuery) -> SearchPage:
        page_number = int(query.cursor) if query.cursor else 0
        already_returned = page_number * query.page_size
        remaining = max(0, query.result_limit - already_returned)
        count_this_page = min(query.page_size, remaining)

        rng = random.Random(_seed_for(query, page_number))
        businesses = [
            self._generate_business(query, page_number, i, rng) for i in range(count_this_page)
        ]

        next_page = page_number + 1
        has_more = (
            next_page * query.page_size
        ) < query.result_limit and count_this_page == query.page_size
        return SearchPage(
            businesses=businesses,
            next_cursor=str(next_page) if has_more else None,
            has_more=has_more,
            page_number=page_number,
        )

    def _generate_business(
        self, query: SearchQuery, page_number: int, index: int, rng: random.Random
    ) -> BusinessRecord:
        adjective = rng.choice(_ADJECTIVES)
        suffix = rng.choice(_SUFFIXES)
        industry_label = (query.category or query.industry).title()
        name = f"{adjective} {industry_label} {suffix}"
        native_id = f"mock-{_seed_for(query, page_number)}-{index}"

        rating_floor = query.min_rating or 3.0
        rating = round(rng.uniform(rating_floor, min(5.0, rating_floor + 1.5)), 1)
        review_floor = query.min_reviews or 5
        review_count = review_floor + rng.randint(0, 200)

        has_phone = True if query.must_have_phone else rng.random() > 0.2
        phone = f"+971-4-{rng.randint(1000000, 9999999)}" if has_phone else None

        if query.website_requirement == "required":
            has_website = True
        elif query.website_requirement == "missing":
            has_website = False
        else:
            has_website = rng.random() > 0.35
        website = (
            f"https://www.{name.lower().replace(' ', '-')}.example.com" if has_website else None
        )

        return BusinessRecord(
            source="mock",
            source_native_id=native_id,
            name=name,
            category=query.category or query.industry,
            address=f"{rng.randint(1, 200)} {query.area or query.city} Street",
            country=query.country,
            region=query.region,
            city=query.city,
            area=query.area,
            latitude=round(rng.uniform(24.9, 25.3), 6),
            longitude=round(rng.uniform(55.0, 55.4), 6),
            phone=phone,
            website=website,
            google_maps_url=f"https://maps.example.com/?q={native_id}",
            rating=rating,
            review_count=review_count,
            business_status=query.business_status or "operational",
            source_url=f"https://mock-source.example.com/place/{native_id}",
            collected_at=datetime.now(UTC).isoformat(),
        )
