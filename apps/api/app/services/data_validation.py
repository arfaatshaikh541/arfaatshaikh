"""Source-sensitive data validation. Pure helpers are unit-tested; `validate_database` runs the same rules against
a live database (scripts/validate_data.py) and must report zero violations before a release.

Each check returns a list of human-readable violations; an empty list means the rule holds.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from typing import Iterable

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_contract import DataSet, DirectoryListing, KnowledgeRecord
from app.models.hadith import HadithCollection, HadithGrading, HadithNarration
from app.models.knowledge_network import CanonicalKnowledgeEntity, KnowledgeRelationship
from app.models.quran import QuranAyah, QuranTextEdition
from app.models.sources import SourceEdition, SourcePassage
from app.services.data_contracts import QURAN_REF, can_publish, dedupe_key, haversine_km
from app.services.manifest import validate_manifest
from app.services.publication_policy import desired_visibility


def find_duplicates(values: Iterable[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def missing_metadata(rows: Iterable[dict], required: tuple[str, ...], label: str) -> list[str]:
    problems = []
    for row in rows:
        gaps = [key for key in required if not str(row.get(key) or "").strip()]
        if gaps:
            problems.append(f"{label} {row.get('id', '?')}: missing {', '.join(gaps)}")
    return problems


def grading_problems(rows: Iterable[dict]) -> list[str]:
    """A hadith grade is a scholarly judgement: it needs a named grader and a citable source passage."""
    problems = []
    for row in rows:
        if not str(row.get("grader_name") or "").strip():
            problems.append(f"grading {row.get('id', '?')}: no named grader")
        if not row.get("source_passage_id"):
            problems.append(f"grading {row.get('id', '?')}: no source")
        if not str(row.get("grading_label") or "").strip():
            problems.append(f"grading {row.get('id', '?')}: no grade label")
    return problems


def citation_problems(cited_labels: Iterable[str], available_labels: Iterable[str]) -> list[str]:
    available = set(available_labels)
    return [f"citation {label} points to a nonexistent source" for label in cited_labels if label not in available]


def manifest_problems(manifest: dict) -> list[str]:
    return validate_manifest(manifest)


# ------------------------------------------------------------------ database checks
async def quran_text_sources(db: AsyncSession) -> list[str]:
    problems: list[str] = []
    editions = (await db.execute(select(QuranTextEdition, SourceEdition).join(SourceEdition, SourceEdition.id == QuranTextEdition.source_edition_id)
                                 .where(QuranTextEdition.published.is_(True)))).all()
    for edition, source in editions:
        if source.review_status != "approved" or source.ingestion_status != "ready":
            problems.append(f"Qur'an text edition {edition.edition_key}: source edition is {source.review_status}/{source.ingestion_status}, not approved/ready")
    unlinked = await db.scalar(select(func.count()).select_from(QuranAyah).outerjoin(SourcePassage, SourcePassage.id == QuranAyah.source_passage_id).where(SourcePassage.id.is_(None)))
    if unlinked:
        problems.append(f"{unlinked} ayahs have no source passage")
    bad = 0
    for text, digest in (await db.execute(select(QuranAyah.arabic_text, QuranAyah.text_sha256))).all():
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != digest:
            bad += 1
    if bad:
        problems.append(f"{bad} ayahs whose text does not match its recorded sha256")
    return problems


async def hadith_grading_sources(db: AsyncSession) -> list[str]:
    rows = (await db.execute(select(HadithGrading.id, HadithGrading.grader_name, HadithGrading.grading_label, HadithGrading.source_passage_id).where(HadithGrading.published.is_(True)))).all()
    return grading_problems([{"id": str(r[0]), "grader_name": r[1], "grading_label": r[2], "source_passage_id": r[3]} for r in rows])


async def published_content_has_approved_source(db: AsyncSession) -> list[str]:
    """Every published reader row must trace to a current passage of an approved, ready source edition."""
    from app.models.hadith import HadithNarration, HadithTranslation
    from app.models.quran import QuranAyahTranslation
    from app.models.tafsir import TafsirEntry
    problems = []
    for name, model in (("hadith narration", HadithNarration), ("hadith translation", HadithTranslation), ("Qur'an translation", QuranAyahTranslation), ("tafsir entry", TafsirEntry)):
        count = await db.scalar(select(func.count()).select_from(model).join(SourcePassage, SourcePassage.id == model.source_passage_id).join(SourceEdition, SourceEdition.id == SourcePassage.edition_id)
                                .where(model.published.is_(True), (SourceEdition.review_status != "approved") | (SourceEdition.ingestion_status != "ready") | SourcePassage.is_current.is_(False)))
        if count:
            problems.append(f"{count} published {name} rows trace to an unapproved source or a non-current passage")
    return problems


async def hidden_datasets_have_no_published_rows(db: AsyncSession, manifest: dict) -> list[str]:
    """What the manifest/DB says is hidden must really be hidden in the content tables."""
    from app.services.publication_policy import published_row_count
    datasets = {d.dataset_key: d for d in (await db.scalars(select(DataSet))).all()}
    problems = []
    for entry in manifest["datasets"]:
        if not entry.get("targets"):
            continue
        if not desired_visibility(datasets.get(entry["id"])):
            for target in entry["targets"]:
                count = await published_row_count(db, target)
                if count:
                    problems.append(f"dataset {entry['id']} is not published but {count} {target['kind']} rows are visible")
    return problems


async def knowledge_record_metadata(db: AsyncSession) -> list[str]:
    rows = (await db.execute(select(KnowledgeRecord, DataSet).join(DataSet, DataSet.id == KnowledgeRecord.dataset_id).where(DataSet.publication_status == "published"))).all()
    problems = missing_metadata(({"id": r.record_key, "source": r.source, "license": r.license, "provenance": r.provenance, "title": r.title, "description": r.description} for r, _ in rows),
                                ("source", "license", "provenance", "title", "description"), "knowledge record")
    for record, dataset in rows:
        allowed, reasons = can_publish(license_status=dataset.license_status, validation_status=dataset.validation_status, rights_confirmation=dataset.rights_confirmation)
        if not allowed:
            problems.append(f"record {record.record_key} is public through dataset {dataset.dataset_key}, which cannot be published: {'; '.join(reasons)}")
            break
    return problems


async def directory_metadata(db: AsyncSession) -> list[str]:
    rows = (await db.scalars(select(DirectoryListing).where(DirectoryListing.status == "published"))).all()
    return missing_metadata(({"id": str(r.id), "source": r.source, "license": r.license, "provenance": r.provenance, "name": r.name} for r in rows), ("source", "license", "provenance", "name"), "directory listing")


async def duplicate_identifiers(db: AsyncSession) -> list[str]:
    problems = []
    for label, column in (("knowledge entity key", CanonicalKnowledgeEntity.canonical_key), ("dataset key", DataSet.dataset_key)):
        dupes = (await db.execute(select(column).group_by(column).having(func.count() > 1))).scalars().all()
        problems += [f"duplicate {label}: {d}" for d in dupes]
    ayah_dupes = (await db.execute(select(QuranAyah.text_edition_id, QuranAyah.canonical_reference).group_by(QuranAyah.text_edition_id, QuranAyah.canonical_reference).having(func.count() > 1))).all()
    problems += [f"duplicate ayah reference {ref}" for _, ref in ayah_dupes]
    return problems


async def graph_provenance(db: AsyncSession) -> list[str]:
    missing = await db.scalar(select(func.count()).select_from(KnowledgeRelationship).outerjoin(SourcePassage, SourcePassage.id == KnowledgeRelationship.evidence_passage_id)
                              .where(SourcePassage.id.is_(None)))
    unreviewed = await db.scalar(select(func.count()).select_from(KnowledgeRelationship).where(KnowledgeRelationship.published.is_(True), KnowledgeRelationship.review_status != "approved"))
    problems = []
    if missing:
        problems.append(f"{missing} relationships have no evidence passage")
    if unreviewed:
        problems.append(f"{unreviewed} published relationships are not approved")
    return problems


# ------------------------------------------------------------------ data-completion checks (pure helpers + database rules)
MOSQUE_DUPLICATE_RADIUS_KM = 0.05


def url_problems(label: str, ident: str, urls: dict[str, object]) -> list[str]:
    from urllib.parse import urlparse
    problems = []
    for name, value in urls.items():
        if value in (None, ""):
            continue
        parsed = urlparse(str(value))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            problems.append(f"{label} {ident}: {name} is not a valid http(s) URL")
    return problems


def quran_ref_problems(refs: Iterable[object], ayah_counts: dict[int, int]) -> list[str]:
    """Every cited ayah must exist: surah 1-114 and an ayah number within that surah."""
    problems = []
    for ref in refs:
        if not isinstance(ref, str) or not QURAN_REF.match(ref):
            problems.append(f"malformed Qur'an reference {ref!r}")
            continue
        surah, rest = ref.split(":")
        last = int(rest.split("-")[-1])
        if int(surah) not in ayah_counts:
            problems.append(f"Qur'an reference {ref} names a surah that is not loaded")
        elif last > ayah_counts[int(surah)]:
            problems.append(f"Qur'an reference {ref} is past the end of surah {surah} ({ayah_counts[int(surah)]} ayahs)")
    return problems


def same_place_duplicates(items: Iterable[tuple[str, str, float | None, float | None]], radius_km: float) -> list[str]:
    """(id, dedupe_key, lat, lon): same normalised name and within radius_km (or coordinates unknown) is a duplicate."""
    groups: dict[str, list[tuple[str, float | None, float | None]]] = {}
    for ident, key, lat, lon in items:
        groups.setdefault(key, []).append((ident, lat, lon))
    problems = []
    for key, members in groups.items():
        for index, (ident, lat, lon) in enumerate(members):
            for other, olat, olon in members[:index]:
                if lat is None or olat is None or lon is None or olon is None or haversine_km(lat, lon, olat, olon) <= radius_km:
                    problems.append(f"possible duplicate: {ident} and {other} ({key})")
                    break
    return problems


async def knowledge_reference_checks(db: AsyncSession) -> list[str]:
    """Qur'an and hadith references inside records must exist; relationship targets must resolve (no orphans)."""
    rows = (await db.scalars(select(KnowledgeRecord))).all()
    if not rows:
        return []
    surah_number = cast(func.regexp_replace(QuranAyah.canonical_reference, ':.*$', ''), Integer)
    counts = {int(k): int(v) for k, v in (await db.execute(select(surah_number, func.max(QuranAyah.ayah_number)).group_by(surah_number))).all()}
    collections = {c.collection_key: c.id for c in (await db.scalars(select(HadithCollection))).all()}
    keys = {r.record_key for r in rows} | set((await db.scalars(select(CanonicalKnowledgeEntity.canonical_key))).all())
    problems: list[str] = []
    for record in rows:
        attrs = record.attributes or {}
        for issue in quran_ref_problems(attrs.get("quran_refs", []) or [], counts):
            problems.append(f"record {record.record_key}: {issue}")
        for ref in attrs.get("hadith_refs", []) or []:
            collection_id = collections.get(str(ref.get("collection")))
            if collection_id is None:
                continue  # a collection that is not loaded cannot be checked; the reference stays an unresolved citation
            number = int(ref["number"]) if str(ref.get("number", "")).isdigit() else None
            exists = number is not None and await db.scalar(select(func.count()).select_from(HadithNarration).where(HadithNarration.collection_id == collection_id, HadithNarration.collection_hadith_number == number))
            if not exists:
                problems.append(f"record {record.record_key}: hadith reference {ref.get('collection')} {ref.get('number')} does not exist")
        for rel in record.relationships or []:
            if rel.get("target_id") not in keys:
                problems.append(f"record {record.record_key}: relationship target {rel.get('target_id')} does not exist")
        problems += url_problems("record", record.record_key, {"source_url": record.source_url, "external_url": attrs.get("external_url")})
        if record.entity_type in {"fiqh", "aqeedah", "seerah", "hadith_grading", "terminology", "library_work", "history", "civilization", "scholar"} and not (record.source_work or "").strip():
            problems.append(f"record {record.record_key}: religious record without source_work")
    return problems[:200]


async def duplicate_scholars_books(db: AsyncSession) -> list[str]:
    rows = (await db.scalars(select(KnowledgeRecord).where(KnowledgeRecord.entity_type.in_(("scholar", "library_work", "book"))))).all()
    seen: dict[tuple[str, str], str] = {}
    problems = []
    for r in rows:
        key = (r.entity_type, dedupe_key(r.title, r.author or "", None))
        if key in seen and seen[key] != r.record_key:
            problems.append(f"possible duplicate {r.entity_type}: {r.record_key} and {seen[key]}")
        seen.setdefault(key, r.record_key)
    return problems


async def directory_integrity(db: AsyncSession) -> list[str]:
    """URLs, coordinates, dates and duplicate organisations/mosque locations across every listing."""
    rows = (await db.scalars(select(DirectoryListing).where(DirectoryListing.duplicate_of_id.is_(None), DirectoryListing.status.in_(("pending", "published"))))).all()
    problems: list[str] = []
    for r in rows:
        attrs = r.attributes or {}
        problems += url_problems("listing", str(r.id), {"website": r.website, "source_url": r.source_url, "application_url": attrs.get("application_url"), "registration_url": attrs.get("registration_url")})
        if r.latitude is not None and not (-90 <= r.latitude <= 90 and -180 <= (r.longitude or 0) <= 180):
            problems.append(f"listing {r.id}: coordinates out of range")
        if r.starts_at and r.ends_at and r.ends_at < r.starts_at:
            problems.append(f"listing {r.id}: ends before it starts")
        if r.listing_type == "job" and not (attrs.get("employer") and attrs.get("application_url") and r.expires_at):
            problems.append(f"listing {r.id}: job without employer, application_url or expires_at")
        if r.listing_type == "mosque" and attrs.get("denomination") and not attrs.get("denomination_source"):
            problems.append(f"listing {r.id}: denomination without a stated source")
    by_type: dict[str, list[tuple[str, str, float | None, float | None]]] = {}
    for r in rows:
        by_type.setdefault(r.listing_type, []).append((str(r.id), r.dedupe_key, r.latitude, r.longitude))
    for listing_type, items in by_type.items():
        problems += [f"{listing_type} {p}" for p in same_place_duplicates(items, MOSQUE_DUPLICATE_RADIUS_KM if listing_type == "mosque" else 0.2)[:50]]
    return problems[:200]


async def manifest_record_counts(db: AsyncSession, manifest: dict) -> list[str]:
    """The record count the manifest declares for a dataset must equal what is stored (no silent drift after an import or rollback)."""
    stored = {d.dataset_key: d.record_count for d in (await db.scalars(select(DataSet))).all()}
    return [f"dataset {e['id']}: manifest declares {e['records']} records, database holds {stored.get(e['id'], 0)}"
            for e in manifest["datasets"] if "records" in e and stored.get(e["id"], 0) != e["records"]]


async def domain_registry_matches_database(db: AsyncSession, manifest: dict) -> list[str]:
    """The readiness registry must be internally consistent, agree with the manifest, and agree with the live data it describes."""
    from app.services.readiness import evaluate_domain, live_state, load_registry, validate_registry
    registry = load_registry()
    problems = validate_registry(registry, manifest)
    live = await live_state(db)
    for domain in registry["domains"]:
        result = evaluate_domain(domain, live)
        if result["registry_out_of_date"]:
            problems.append(f"domain {domain['domain']}: registry counts {domain['records']['total']}/{domain['records']['published']} differ from the database {result['counts']['total']}/{result['counts']['published']}")
        if result["status"] != domain["status"]:
            problems.append(f"domain {domain['domain']}: declared {domain['status']} but the live data supports only {result['status']} ({'; '.join(result['downgrade_reasons'])})")
    return problems


async def validate_database(db: AsyncSession, manifest: dict) -> dict[str, list[str]]:
    return {
        "manifest": manifest_problems(manifest),
        "quran_text_has_verified_source": await quran_text_sources(db),
        "hadith_grades_have_sources": await hadith_grading_sources(db),
        "published_content_traces_to_approved_source": await published_content_has_approved_source(db),
        "hidden_datasets_are_hidden": await hidden_datasets_have_no_published_rows(db, manifest),
        "knowledge_records_have_metadata": await knowledge_record_metadata(db),
        "directory_listings_have_metadata": await directory_metadata(db),
        "no_duplicate_identifiers": await duplicate_identifiers(db),
        "graph_relationships_have_provenance": await graph_provenance(db),
        "manifest_record_counts_match": await manifest_record_counts(db, manifest),
        "domain_registry_matches_database": await domain_registry_matches_database(db, manifest),
        "knowledge_references_resolve": await knowledge_reference_checks(db),
        "no_duplicate_scholars_or_books": await duplicate_scholars_books(db),
        "directory_fields_and_duplicates": await directory_integrity(db),
    }
