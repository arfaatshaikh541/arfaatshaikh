"""Data contracts for source-sensitive content, with no database dependency (fully unit-testable).

Rules enforced here are the same ones the importer, the admin API and tests/test_data_validation.py use:
 - a record without provenance/source/licence is rejected, never defaulted;
 - a dataset is publishable only when its licence status permits it and its validation passed;
 - a dataset whose licence is not clearly open needs a recorded owner rights confirmation.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Sequence
from datetime import date as Date
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.content_contract import LISTING_TYPES, RECORD_TYPES

IMPORTER_VERSION = "contract-importer-1.0"

OPEN_LICENCE_STATUSES = frozenset({"VERIFIED_OPEN", "PUBLIC_DOMAIN", "PD_WORK_OPEN_EDITION_DECLARED"})
CONFIRMABLE_LICENCE_STATUSES = frozenset({"OWNER_PERMISSION_GRANTED"})
PUBLISHABLE_LICENCE_STATUSES = OPEN_LICENCE_STATUSES | CONFIRMABLE_LICENCE_STATUSES
SCHOLARLY_STATUSES = ("unreviewed", "reviewed", "scholar_verified", "disputed", "rejected")
RELATION_TYPES = ("authored", "discusses", "relates_to", "explained_by", "part_of", "located_in", "affiliated_with",
                  "supports", "references", "derived_from", "narrated_by", "mentions")


def can_publish(*, license_status: str, validation_status: str, rights_confirmation: dict | None) -> tuple[bool, tuple[str, ...]]:
    """Whether a dataset may be shown publicly. Returns (allowed, reasons it is not allowed)."""
    reasons: list[str] = []
    if license_status not in PUBLISHABLE_LICENCE_STATUSES:
        reasons.append(f"licence status {license_status} does not permit publication")
    if license_status in CONFIRMABLE_LICENCE_STATUSES:
        confirmation = rights_confirmation or {}
        if not all(str(confirmation.get(key, "")).strip() for key in ("confirmed_by", "confirmed_on", "basis")):
            reasons.append("owner permission needs confirmed_by, confirmed_on and basis")
    if validation_status != "VERIFIED":
        reasons.append(f"validation status is {validation_status}, not VERIFIED")
    return (not reasons, tuple(reasons))


class RelationshipInput(BaseModel):
    relation_type: str
    target_id: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=500)
    source_url: str | None = Field(default=None, max_length=800)

    @field_validator("relation_type")
    @classmethod
    def known_relation(cls, value: str) -> str:
        if value not in RELATION_TYPES:
            raise ValueError(f"relation_type must be one of {', '.join(RELATION_TYPES)}")
        return value


def _https_or_none(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("must be an http(s) URL")
    return value


class KnowledgeRecordInput(BaseModel):
    """One record of the contract: ID, TITLE, ARABIC_TITLE, DESCRIPTION, SOURCE, SOURCE_URL, AUTHOR, DATE,
    LICENSE, PROVENANCE, SCHOLARLY_STATUS, CONFIDENCE, LAST_VERIFIED, TAGS, RELATIONSHIPS."""
    id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:\-]*$")
    entity_type: str
    title: str = Field(min_length=1, max_length=500)
    arabic_title: str | None = Field(default=None, max_length=500)
    description: str = Field(min_length=1, max_length=20000)
    source: str = Field(min_length=1, max_length=500)
    source_url: str | None = Field(default=None, max_length=800)
    author: str | None = Field(default=None, max_length=300)
    date: str | None = Field(default=None, max_length=80)
    license: str = Field(min_length=1, max_length=240)
    provenance: str = Field(min_length=3, max_length=4000)
    scholarly_status: str = "unreviewed"
    confidence: int = Field(default=0, ge=0, le=100)
    last_verified: Date | None = None
    tags: list[str] = Field(default_factory=list, max_length=40)
    relationships: list[RelationshipInput] = Field(default_factory=list, max_length=100)

    @field_validator("entity_type")
    @classmethod
    def known_type(cls, value: str) -> str:
        if value not in RECORD_TYPES:
            raise ValueError(f"entity_type must be one of {', '.join(RECORD_TYPES)}")
        return value

    @field_validator("scholarly_status")
    @classmethod
    def known_status(cls, value: str) -> str:
        if value not in SCHOLARLY_STATUSES:
            raise ValueError(f"scholarly_status must be one of {', '.join(SCHOLARLY_STATUSES)}")
        return value

    @field_validator("source_url")
    @classmethod
    def url(cls, value: str | None) -> str | None:
        return _https_or_none(value)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        cleaned = [" ".join(tag.split()).lower() for tag in value if tag and tag.strip()]
        if any(len(tag) > 80 for tag in cleaned):
            raise ValueError("tags are limited to 80 characters")
        return sorted(set(cleaned))

    @model_validator(mode="after")
    def verified_needs_evidence(self):
        if self.scholarly_status in {"reviewed", "scholar_verified"} and not self.last_verified:
            raise ValueError("a reviewed record needs last_verified")
        return self

    def content_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


@dataclass
class BatchResult:
    valid: list[KnowledgeRecordInput] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)


def validate_record_batch(rows: Sequence[object], *, expected_type: str | None = None) -> BatchResult:
    """Validate rows independently so one bad record never hides the others; duplicates are reported."""
    result = BatchResult()
    seen: set[str] = set()
    for position, row in enumerate(rows):
        if not isinstance(row, dict):
            result.failures.append({"index": position, "id": None, "errors": ["record must be a JSON object"]})
            continue
        try:
            record = KnowledgeRecordInput.model_validate(row)
        except Exception as exc:  # pydantic.ValidationError, kept generic to report every message
            errors = [f"{'.'.join(str(p) for p in e.get('loc', ()))}: {e.get('msg')}" for e in getattr(exc, "errors", lambda: [])()] or [str(exc)]
            result.failures.append({"index": position, "id": row.get("id"), "errors": errors})
            continue
        if expected_type and record.entity_type != expected_type:
            result.failures.append({"index": position, "id": record.id, "errors": [f"entity_type {record.entity_type} does not match dataset type {expected_type}"]})
            continue
        if record.id in seen:
            result.failures.append({"index": position, "id": record.id, "errors": ["duplicate id in file"]})
            continue
        seen.add(record.id)
        result.valid.append(record)
    return result


# ---------------------------------------------------------------- directory contract

def normalise_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "").lower()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\b(the|al|masjid|mosque|islamic|centre|center|trust|ltd|limited|inc)\b", " ", text)
    return " ".join(text.split())


def dedupe_key(name: str, city: str | None, country: str | None) -> str:
    return "|".join((normalise_name(name), normalise_name(city or ""), (country or "").lower()))[:300]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


class DirectoryListingInput(BaseModel):
    external_key: str | None = Field(default=None, max_length=200)
    listing_type: str
    name: str = Field(min_length=2, max_length=300)
    arabic_name: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    category: str | None = Field(default=None, max_length=120)
    tags: list[str] = Field(default_factory=list, max_length=30)
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    phone: str | None = Field(default=None, max_length=60)
    email: str | None = Field(default=None, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    website: str | None = Field(default=None, max_length=500)
    source: str = Field(min_length=2, max_length=500)
    source_url: str | None = Field(default=None, max_length=800)
    license: str = Field(min_length=2, max_length=240)
    provenance: str = Field(min_length=3, max_length=4000)
    source_updated_at: Date | None = None

    @field_validator("listing_type")
    @classmethod
    def known_listing(cls, value: str) -> str:
        if value not in LISTING_TYPES:
            raise ValueError(f"listing_type must be one of {', '.join(LISTING_TYPES)}")
        return value

    @field_validator("country")
    @classmethod
    def upper_country(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("website", "source_url")
    @classmethod
    def urls(cls, value: str | None) -> str | None:
        return _https_or_none(value)

    @model_validator(mode="after")
    def coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be given together")
        return self

    @property
    def key(self) -> str:
        return dedupe_key(self.name, self.city, self.country)
