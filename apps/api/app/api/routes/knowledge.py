"""Public read API for the knowledge-record contract, dataset readiness and the knowledge graph.

Only records of enabled, published datasets are ever returned. When nothing is published the response says
why (`readiness`) so the UI can show an honest empty state instead of an error.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select

from app.api.dependencies.auth import DbSession
from app.core.config import get_settings
from app.core.errors import ApplicationError
from app.core.rate_limit import rate_limiter
from app.models.content_contract import DataSet, KnowledgeRecord, RECORD_TYPES
from app.models.knowledge_network import CanonicalKnowledgeEntity, KnowledgeRelationship
from app.models.sources import SourcePassage
from app.services.manifest import load_manifest

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

def _published_dataset():
    return (DataSet.publication_status == "published", DataSet.enabled.is_(True))


def record_view(record: KnowledgeRecord, dataset: DataSet) -> dict:
    return {
        "id": record.record_key, "dataset": dataset.dataset_key, "type": record.entity_type, "title": record.title, "arabic_title": record.arabic_title,
        "description": record.description, "source": record.source, "source_url": record.source_url, "author": record.author, "date": record.record_date,
        "license": record.license, "provenance": record.provenance, "scholarly_status": record.scholarly_status, "confidence": record.confidence,
        "last_verified": record.last_verified.isoformat() if record.last_verified else None, "tags": record.tags, "relationships": record.relationships,
        "source_work": record.source_work, "edition": record.edition, "volume": record.volume, "page": record.page, "chapter": record.chapter,
        "language": record.language, "publication_status": record.publication_status, "license_status": record.license_status,
        "provenance_status": record.provenance_status, "attributes": record.attributes or {},
    }


@router.get("/readiness")
async def readiness(db: DbSession, entity_type: str | None = None):
    """Per dataset: what it is, whether it is public and, if not, exactly what is missing."""
    stmt = select(DataSet).order_by(DataSet.dataset_key)
    rows = (await db.scalars(stmt)).all()
    items = [{"id": d.dataset_key, "name": d.name, "type": d.entity_type, "public": d.publication_status == "published" and d.enabled,
              "readiness": d.readiness, "license_status": d.license_status, "validation_status": d.validation_status, "record_count": d.record_count,
              "remaining_action": d.remaining_action,
              # a domain with no loaded dataset says so plainly instead of implying content exists
              "data_source_required": d.record_count == 0} for d in rows if not entity_type or d.entity_type == entity_type]
    return {"datasets": items}


@router.get("/records")
async def list_records(request: Request, db: DbSession, type: Annotated[str | None, Query(max_length=40)] = None, q: Annotated[str | None, Query(max_length=200)] = None,
                       tag: Annotated[str | None, Query(max_length=80)] = None,
                       madhhab: Annotated[str | None, Query(max_length=80)] = None, school: Annotated[str | None, Query(max_length=80)] = None,
                       topic: Annotated[str | None, Query(max_length=200)] = None, collection: Annotated[str | None, Query(max_length=80)] = None,
                       hadith_number: Annotated[str | None, Query(max_length=40)] = None, page: Annotated[int, Query(ge=1, le=10000)] = 1, page_size: Annotated[int, Query(ge=1, le=50)] = 20):
    await rate_limiter.check(request, "knowledge", max(get_settings().auth_rate_limit * 6, 60), 60)
    if type and type not in RECORD_TYPES:
        raise ApplicationError("invalid_type", "Unknown record type.", 422)
    conditions = [*_published_dataset()]
    if type:
        conditions.append(KnowledgeRecord.entity_type == type)
    if tag:
        conditions.append(KnowledgeRecord.tags.contains([tag.lower()]))
    for key, value in (("madhhab", madhhab), ("school", school), ("topic", topic), ("collection", collection), ("hadith_number", hadith_number)):
        if value:
            # each scholarly position stays its own row; filtering never merges or ranks opposing views
            conditions.append(KnowledgeRecord.attributes.contains({key: int(value) if key == "hadith_number" and value.isdigit() else value}))
    if q and q.strip():
        document = func.to_tsvector("simple", KnowledgeRecord.title + " " + func.coalesce(KnowledgeRecord.arabic_title, "") + " " + KnowledgeRecord.description)
        conditions.append(document.op("@@")(func.plainto_tsquery("simple", q.strip())))
    base = select(KnowledgeRecord, DataSet).join(DataSet, DataSet.id == KnowledgeRecord.dataset_id).where(*conditions)
    total = await db.scalar(select(func.count()).select_from(KnowledgeRecord).join(DataSet, DataSet.id == KnowledgeRecord.dataset_id).where(*conditions)) or 0
    rows = (await db.execute(base.order_by(KnowledgeRecord.title).limit(page_size).offset((page - 1) * page_size))).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [record_view(r, d) for r, d in rows]}


@router.get("/records/{dataset_key}/{record_key}")
async def get_record(dataset_key: str, record_key: str, db: DbSession):
    row = (await db.execute(select(KnowledgeRecord, DataSet).join(DataSet, DataSet.id == KnowledgeRecord.dataset_id)
                            .where(DataSet.dataset_key == dataset_key, KnowledgeRecord.record_key == record_key, *_published_dataset()))).first()
    if row is None:
        raise ApplicationError("record_not_found", "Record not found.", 404)
    return record_view(*row)


@router.get("/graph/stats")
async def graph_stats(db: DbSession):
    entities = (await db.execute(select(CanonicalKnowledgeEntity.entity_type, func.count()).where(CanonicalKnowledgeEntity.publication_status == "published").group_by(CanonicalKnowledgeEntity.entity_type))).all()
    relations = (await db.execute(select(KnowledgeRelationship.relationship_type, func.count()).where(KnowledgeRelationship.published.is_(True), KnowledgeRelationship.review_status == "approved").group_by(KnowledgeRelationship.relationship_type))).all()
    return {"entities": {k: v for k, v in entities}, "relationships": {k: v for k, v in relations}}


@router.get("/graph/entity")
async def graph_entity(db: DbSession, key: Annotated[str, Query(min_length=3, max_length=220)], limit: Annotated[int, Query(ge=1, le=100)] = 25):
    """One entity with its published, approved relationships. Every relationship carries its evidence passage."""
    entity = await db.scalar(select(CanonicalKnowledgeEntity).where(CanonicalKnowledgeEntity.canonical_key == key, CanonicalKnowledgeEntity.publication_status == "published"))
    if entity is None:
        raise ApplicationError("entity_not_found", "Entity not found.", 404)
    out = []
    for direction, mine, other in (("outgoing", KnowledgeRelationship.source_entity_id, KnowledgeRelationship.target_entity_id),
                                   ("incoming", KnowledgeRelationship.target_entity_id, KnowledgeRelationship.source_entity_id)):
        rows = (await db.execute(select(KnowledgeRelationship, CanonicalKnowledgeEntity, SourcePassage)
                                 .join(CanonicalKnowledgeEntity, CanonicalKnowledgeEntity.id == other)
                                 .join(SourcePassage, SourcePassage.id == KnowledgeRelationship.evidence_passage_id)
                                 .where(mine == entity.id, KnowledgeRelationship.published.is_(True), KnowledgeRelationship.review_status == "approved", CanonicalKnowledgeEntity.publication_status == "published")
                                 .order_by(KnowledgeRelationship.relationship_type, CanonicalKnowledgeEntity.canonical_key).limit(limit))).all()
        for rel, node, passage in rows:
            out.append({"direction": direction, "type": rel.relationship_type, "confidence": rel.confidence, "rationale": rel.rationale,
                        "evidence": {"passage_key": passage.passage_key, "citation": passage.citation_label},
                        "entity": {"key": node.canonical_key, "type": node.entity_type, "label": node.english_label, "arabic_label": node.arabic_label, "url": node.canonical_url}})
    return {"entity": {"key": entity.canonical_key, "type": entity.entity_type, "label": entity.english_label, "arabic_label": entity.arabic_label, "url": entity.canonical_url}, "relationships": out}


@router.get("/manifest")
async def public_manifest():
    """The public face of data/source-manifest.json: what each source is, its licence and whether it is published."""
    manifest = load_manifest()
    keep = ("id", "name", "purpose", "category", "source", "license", "provenance", "validation_status", "publication_status", "readiness", "public", "date_acquired", "last_checked", "remaining_action")
    return {"as_of": manifest["as_of"], "datasets": [{k: d.get(k) for k in keep} for d in manifest["datasets"]]}
