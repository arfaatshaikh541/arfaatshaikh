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
from datetime import datetime, timezone
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.content_contract import LICENSE_STATUSES, LISTING_TYPES, PROVENANCE_STATUSES, PUBLICATION_FORMS, RECORD_TYPES

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
    # source-level provenance of religious content
    source_work: str | None = Field(default=None, max_length=500)
    edition: str | None = Field(default=None, max_length=300)
    volume: str | None = Field(default=None, max_length=80)
    page: str | None = Field(default=None, max_length=80)
    chapter: str | None = Field(default=None, max_length=300)
    language: str | None = Field(default=None, max_length=24)
    publication_status: str = "unspecified"
    license_status: str = "UNKNOWN"
    provenance_status: str = "unclear"
    attributes: dict = Field(default_factory=dict)

    @field_validator("entity_type")
    @classmethod
    def known_type(cls, value: str) -> str:
        if value not in RECORD_TYPES:
            raise ValueError(f"entity_type must be one of {', '.join(RECORD_TYPES)}")
        return value

    @field_validator("publication_status")
    @classmethod
    def known_publication(cls, value: str) -> str:
        if value not in PUBLICATION_FORMS:
            raise ValueError(f"publication_status must be one of {', '.join(PUBLICATION_FORMS)}")
        return value

    @field_validator("license_status")
    @classmethod
    def known_license(cls, value: str) -> str:
        if value not in LICENSE_STATUSES:
            raise ValueError(f"license_status must be one of {', '.join(LICENSE_STATUSES)}")
        return value

    @field_validator("provenance_status")
    @classmethod
    def known_provenance(cls, value: str) -> str:
        if value not in PROVENANCE_STATUSES:
            raise ValueError(f"provenance_status must be one of {', '.join(PROVENANCE_STATUSES)}")
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

    @model_validator(mode="after")
    def type_rules(self):
        problems = check_record_structure(self)
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def content_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()



# ---------------------------------------------------------------- religious-content structure

SOURCED_TYPES = frozenset({"fiqh", "aqeedah", "seerah", "hadith_grading", "terminology", "library_work", "history", "civilization", "scholar"})
SEERAH_RELIABILITY = ("established", "well_known_disputed", "weak_reports")
LIBRARY_AVAILABILITY = ("metadata_only", "external_link", "owner_file")
# One grade entry: who graded, what they said and where the grading is published. Work, edition and page stay empty unless the source states them.
GRADE_FIELDS = frozenset({"grader", "grade", "grading_source", "grading_work", "grading_edition", "page_reference", "source_reference_text", "provenance", "note", "rights_status", "verification_status"})
GRADE_RIGHTS = ("unverified", "open", "permission_granted", "restricted")
GRADE_VERIFICATION = ("unverified", "checked_against_source", "disputed")
QURAN_REF = re.compile(r"^(?:[1-9]|[1-9]\d|10\d|11[0-4]):[1-9]\d{0,2}(?:-[1-9]\d{0,2})?$")
ISBN = re.compile(r"^(?:97[89])?\d{9}[\dXx]$")


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _refs(attributes: dict) -> list[str]:
    problems: list[str] = []
    for ref in attributes.get("quran_refs", []) or []:
        if not isinstance(ref, str) or not QURAN_REF.match(ref):
            problems.append(f"quran_refs entry {ref!r} must look like 2:255 or 2:255-257")
        elif "-" in ref:
            start, end = ref.split(":")[1].split("-")
            if int(end) < int(start):
                problems.append(f"quran_refs entry {ref!r} ends before it starts")
    for ref in attributes.get("hadith_refs", []) or []:
        if not (isinstance(ref, dict) and _text(ref.get("collection")) and (isinstance(ref.get("number"), int) or _text(ref.get("number")))):
            problems.append("hadith_refs entries need collection and number")
    return problems


def check_record_structure(record: "KnowledgeRecordInput") -> list[str]:
    """Rules a religious record must satisfy: traceable to a named work, never a generated ruling, disagreement kept apart."""
    attrs = record.attributes or {}
    problems: list[str] = _refs(attrs)
    kind = record.entity_type
    if kind in SOURCED_TYPES:
        if not _text(record.source_work):
            problems.append(f"{kind} records need source_work (the named work the content comes from)")
        if not _text(record.language):
            problems.append(f"{kind} records need language")
        if record.provenance_status == "source_and_page_cited" and not (_text(record.page) or _text(record.chapter)):
            problems.append("provenance_status source_and_page_cited needs page or chapter")
    if kind == "fiqh":
        for key in ("madhhab", "topic", "question", "ruling"):
            if not _text(attrs.get(key)):
                problems.append(f"fiqh records need attributes.{key}")
        if not (_text(record.page) or _text(record.chapter)):
            problems.append("fiqh records need page or chapter so the ruling can be traced")
        for item in attrs.get("evidence", []) or []:
            if not (isinstance(item, dict) and _text(item.get("type")) and (_text(item.get("reference")) or _text(item.get("text")))):
                problems.append("each evidence entry needs type and reference or text")
    elif kind == "aqeedah":
        for key in ("school", "topic", "statement"):
            if not _text(attrs.get(key)):
                problems.append(f"aqeedah records need attributes.{key}")
        if not (_text(record.page) or _text(record.chapter)):
            problems.append("aqeedah records need page or chapter so the statement can be traced")
    elif kind == "seerah":
        if attrs.get("reliability") not in SEERAH_RELIABILITY:
            problems.append(f"seerah records need attributes.reliability, one of {', '.join(SEERAH_RELIABILITY)}")
    elif kind == "hadith_grading":
        grades = attrs.get("grades")
        if not _text(attrs.get("collection")) or attrs.get("hadith_number") in (None, ""):
            problems.append("hadith_grading records need attributes.collection and attributes.hadith_number")
        if not isinstance(grades, list) or not grades:
            problems.append("hadith_grading records need at least one grade (grader, grade, grading_source)")
        else:
            graders: set[str] = set()
            for grade in grades:
                if not (isinstance(grade, dict) and _text(grade.get("grader")) and _text(grade.get("grade")) and _text(grade.get("grading_source"))):
                    problems.append("every grade needs grader, grade and grading_source (a grade is never inferred)")
                    continue
                if grade["grader"] in graders:
                    problems.append(f"grader {grade['grader']} appears twice")
                graders.add(grade["grader"])
                unknown = sorted(set(grade) - GRADE_FIELDS)
                if unknown:
                    problems.append(f"grade fields not allowed: {', '.join(unknown)}")
                if grade.get("rights_status", "unverified") not in GRADE_RIGHTS:
                    problems.append(f"grade rights_status must be one of {', '.join(GRADE_RIGHTS)}")
                if grade.get("verification_status", "unverified") not in GRADE_VERIFICATION:
                    problems.append(f"grade verification_status must be one of {', '.join(GRADE_VERIFICATION)}")
    elif kind == "terminology":
        if not (_text(attrs.get("definition")) or _text(attrs.get("technical_meaning")) or _text(attrs.get("linguistic_meaning"))):
            problems.append("terminology records need a definition, technical_meaning or linguistic_meaning")
    elif kind == "library_work":
        if attrs.get("availability") not in LIBRARY_AVAILABILITY:
            problems.append(f"library_work records need attributes.availability, one of {', '.join(LIBRARY_AVAILABILITY)}")
        if attrs.get("availability") == "external_link" and not _text(attrs.get("external_url")):
            problems.append("an external_link work needs attributes.external_url")
        if attrs.get("availability") == "owner_file" and record.license_status not in PUBLISHABLE_LICENCE_STATUSES:
            problems.append("a stored file needs a licence status that permits redistribution; otherwise use metadata_only or external_link")
        isbn = attrs.get("isbn")
        if isbn and not ISBN.match(str(isbn).replace("-", "").replace(" ", "")):
            problems.append("isbn is not valid")
        for key in ("external_url", "digital_file_reference"):
            if attrs.get(key) and key == "external_url":
                try:
                    _https_or_none(str(attrs[key]))
                except ValueError as exc:
                    problems.append(f"{key} {exc}")
    return problems

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


EMPLOYMENT_TYPES = ("full_time", "part_time", "contract", "internship", "volunteer", "temporary")
LISTING_ATTRIBUTES: dict[str, frozenset[str]] = {
    "mosque": frozenset({"denomination", "denomination_source", "facilities", "hours", "commune", "commune_code", "wilaya_code", "wikidata", "osm", "geoalgeria_id", "geo_precision", "geo_method", "name_fr", "name_ar", "name_en"}),
    "business": frozenset({"hours", "opening_hours", "halal_certification", "halal_certifier", "registration"}),
    "charity": frozenset({"legal_name", "registration_number", "registration_body", "mission", "services", "countries_served"}),
    "job": frozenset({"employer", "employment_type", "salary", "salary_currency", "salary_period", "application_url", "requirements", "remote"}),
    "professional": frozenset({"organization", "specialization", "registration_number", "registration_body", "languages"}),
    "organisation": frozenset({"legal_name", "registration_number", "registration_body", "mission", "services", "parent_organisation"}),
    "event": frozenset({"organizer", "registration_url", "online", "recurrence"}),
    "volunteering": frozenset({"organization", "requirements", "application_url", "commitment", "remote"}),
    "health": frozenset({"organization", "specialization", "registration_number", "registration_body", "languages"}),
}
URL_ATTRIBUTES = ("application_url", "registration_url")


def check_listing_structure(item: "DirectoryListingInput") -> list[str]:
    """Per-type requirements. Nothing here invents a value: a job without an employer or a way to apply is rejected, not completed."""
    attrs = item.attributes or {}
    problems: list[str] = []
    unknown = sorted(set(attrs) - LISTING_ATTRIBUTES.get(item.listing_type, frozenset()))
    if unknown:
        problems.append(f"attributes not allowed for {item.listing_type}: {', '.join(unknown)}")
    for key in URL_ATTRIBUTES:
        if attrs.get(key):
            try:
                _https_or_none(str(attrs[key]))
            except ValueError as exc:
                problems.append(f"attributes.{key} {exc}")
    if item.starts_at and item.ends_at and item.ends_at < item.starts_at:
        problems.append("ends_at is before starts_at")
    if item.listing_type == "job":
        if not _text(attrs.get("employer")):
            problems.append("a job needs attributes.employer")
        if not _text(attrs.get("application_url")):
            problems.append("a job needs attributes.application_url (where to apply)")
        if attrs.get("employment_type") not in (None, *EMPLOYMENT_TYPES):
            problems.append(f"employment_type must be one of {', '.join(EMPLOYMENT_TYPES)}")
        if item.expires_at is None:
            problems.append("a job needs expires_at so it disappears when it closes")
        if attrs.get("salary") is not None and not isinstance(attrs.get("salary"), (int, float, str)):
            problems.append("salary must be a number or text exactly as the employer gave it")
    if item.listing_type == "event" and item.starts_at is None:
        problems.append("an event needs starts_at")
    if item.listing_type == "volunteering":
        if not _text(attrs.get("organization")):
            problems.append("a volunteering opportunity needs attributes.organization")
    if item.listing_type in {"charity", "organisation"} and attrs.get("donation_url"):
        problems.append("donation links are not accepted from imports")
    if item.listing_type == "mosque" and attrs.get("denomination") and not _text(attrs.get("denomination_source")):
        problems.append("a mosque denomination is only kept when its source is stated (denomination_source)")
    return problems


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
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    expires_at: datetime | None = None
    posted_at: datetime | None = None
    last_verified: Date | None = None
    attributes: dict = Field(default_factory=dict)

    @field_validator("listing_type")
    @classmethod
    def known_listing(cls, value: str) -> str:
        if value not in LISTING_TYPES:
            raise ValueError(f"listing_type must be one of {', '.join(LISTING_TYPES)}")
        return value

    @field_validator("starts_at", "ends_at", "expires_at", "posted_at")
    @classmethod
    def utc(cls, value: datetime | None) -> datetime | None:
        """A time without a zone is read as UTC, so comparisons never mix naive and aware values."""
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
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

    @model_validator(mode="after")
    def type_rules(self):
        problems = check_listing_structure(self)
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @property
    def key(self) -> str:
        return dedupe_key(self.name, self.city, self.country)
