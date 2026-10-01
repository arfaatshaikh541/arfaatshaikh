"""Source-sensitive data validation. Pure helpers are unit-tested; `validate_database` runs the same rules against
a live database (scripts/validate_data.py) and must report zero violations before a release.

Each check returns a list of human-readable violations; an empty list means the rule holds.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_contract import DataSet, DirectoryListing, KnowledgeRecord
from app.models.hadith import HadithGrading
from app.models.knowledge_network import CanonicalKnowledgeEntity, KnowledgeRelationship
from app.models.quran import QuranAyah, QuranTextEdition
from app.models.sources import SourceEdition, SourcePassage
from app.services.data_contracts import can_publish
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
    }
