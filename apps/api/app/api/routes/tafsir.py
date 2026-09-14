from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends

from app.api.dependencies.auth import require_csrf
from app.api.dependencies.platform_admin import require_platform_administrator
from app.api.dependencies.auth import DbSession
from app.models.identity import Session, User
from app.schemas.tafsir import *
from app.services.tafsir import TafsirService

router = APIRouter(prefix="/tafsir", tags=["tafsir"])

@router.get("/authors", response_model=list[TafsirAuthorView])
async def list_authors(db: DbSession): return await TafsirService(db).list_authors()

@router.get("/collections", response_model=list[TafsirCollectionView])
async def list_collections(db: DbSession): return await TafsirService(db).list_collections()

@router.get("/collections/{collection_key}", response_model=TafsirCollectionView)
async def get_collection(collection_key: str, db: DbSession): return await TafsirService(db).get_collection(collection_key)

@router.get("/entries/{reference}", response_model=TafsirEntryView)
async def get_entry(reference: str, db: DbSession): return await TafsirService(db).get_entry(reference)

@router.post("/admin/authors", status_code=201)
async def create_author(payload: TafsirAuthorCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await TafsirService(db).create_author(payload); await db.commit(); return {"id": row.id, "published": row.published}

@router.post("/admin/collections", status_code=201)
async def create_collection(payload: TafsirCollectionCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await TafsirService(db).create_collection(payload); await db.commit(); return {"id": row.id, "published": row.published}

@router.post("/admin/editions", status_code=201)
async def create_edition(payload: TafsirEditionCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await TafsirService(db).create_edition(payload); await db.commit(); return {"id": row.id, "published": row.published}

@router.post("/admin/editions/{edition_id}/volumes", status_code=201)
async def create_volume(edition_id: UUID, payload: TafsirVolumeCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await TafsirService(db).create_volume(edition_id, payload); await db.commit(); return {"id": row.id, "published": row.published}

@router.post("/admin/editions/{edition_id}/sections", status_code=201)
async def create_section(edition_id: UUID, payload: TafsirSectionCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await TafsirService(db).create_section(edition_id, payload); await db.commit(); return {"id": row.id, "published": row.published}

@router.post("/admin/editions/{edition_id}/entries", status_code=201)
async def create_entry(edition_id: UUID, payload: TafsirEntryCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await TafsirService(db).create_entry(edition_id, payload); await db.commit(); return {"id": row.id, "reference": row.canonical_reference, "published": row.published}

@router.post("/admin/translation-editions", status_code=201)
async def create_translation_edition(payload: TafsirTranslationEditionCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await TafsirService(db).create_translation_edition(payload); await db.commit(); return {"id": row.id, "published": row.published}

@router.post("/admin/translations", status_code=201)
async def create_translation(payload: TafsirTranslationCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await TafsirService(db).create_translation(payload); await db.commit(); return {"id": row.id, "published": row.published}

from app.api.dependencies.auth import get_current_user
from app.services.tafsir_imports import TafsirImportService

@router.post("/admin/imports", status_code=201)
async def create_tafsir_import(payload: TafsirImportBatchCreate, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await TafsirImportService(db).create_batch(payload, admin.id); await db.commit(); return {"id": row.id, "status": row.status}

@router.post("/admin/imports/{batch_id}/entries", status_code=201)
async def stage_tafsir_entry(batch_id: UUID, payload: TafsirImportEntryCreate, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await TafsirImportService(db).add_entry(batch_id, payload, admin.id); await db.commit(); return {"id": row.id, "reference": row.canonical_reference}

@router.post("/admin/imports/{batch_id}/validate")
async def validate_tafsir_import(batch_id: UUID, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await TafsirImportService(db).validate_batch(batch_id, admin.id); await db.commit(); return {"id": row.id, "status": row.status, "summary": row.validation_summary}

@router.post("/admin/imports/{batch_id}/review-assignments", status_code=201)
async def assign_tafsir_reviewer(batch_id: UUID, payload: TafsirImportReviewAssignmentCreate, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await TafsirImportService(db).assign_reviewer(batch_id, payload, admin.id); await db.commit(); return {"id": row.id, "status": row.status}

@router.get("/me/review-queue")
async def tafsir_review_queue(db: DbSession, user: Annotated[User, Depends(get_current_user)]):
    rows = await TafsirImportService(db).reviewer_queue(user.id); return [{"id": r.id, "batch_id": r.import_batch_id, "domain": r.review_domain, "due_at": r.due_at} for r in rows]

@router.post("/me/review-assignments/{assignment_id}/decision")
async def decide_tafsir_review(assignment_id: UUID, payload: TafsirImportReviewCreate, db: DbSession, user: Annotated[User, Depends(get_current_user)], __: Annotated[Session, Depends(require_csrf)]):
    row = await TafsirImportService(db).review_assignment(assignment_id, user.id, payload); await db.commit(); return {"id": row.id, "status": row.status}

@router.post("/admin/imports/{batch_id}/publish")
async def publish_tafsir_import(batch_id: UUID, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await TafsirImportService(db).publish(batch_id, admin.id); await db.commit(); return {"id": row.id, "status": row.status}

from app.services.tafsir_imports import TafsirTranslationImportService

@router.post("/admin/translation-imports", status_code=201)
async def create_tafsir_translation_import(payload: TafsirTranslationImportBatchCreate, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await TafsirTranslationImportService(db).create_translation_batch(payload, admin.id); await db.commit(); return {"id": row.id, "status": row.status}

@router.post("/admin/translation-imports/{batch_id}/items", status_code=201)
async def stage_tafsir_translation(batch_id: UUID, payload: TafsirTranslationImportItemCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await TafsirTranslationImportService(db).add_translation_item(batch_id, payload); await db.commit(); return {"id": row.id}

@router.post("/admin/translation-imports/{batch_id}/validate")
async def validate_tafsir_translation_import(batch_id: UUID, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await TafsirTranslationImportService(db).validate_translation_batch(batch_id); await db.commit(); return {"id": row.id, "status": row.status, "summary": row.validation_summary}

@router.post("/admin/translation-imports/{batch_id}/review")
async def review_tafsir_translation_import(batch_id: UUID, payload: TafsirImportReviewCreate, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await TafsirTranslationImportService(db).review_translation_batch(batch_id, admin.id, payload); await db.commit(); return {"id": row.id, "status": row.status}

@router.post("/admin/translation-imports/{batch_id}/publish")
async def publish_tafsir_translation_import(batch_id: UUID, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await TafsirTranslationImportService(db).publish_translation_batch(batch_id); await db.commit(); return {"id": row.id, "status": row.status}

from fastapi import Query
from app.services.knowledge_graph import KnowledgeGraphService

@router.get("/topics")
async def list_knowledge_topics(db: DbSession):
    rows = await KnowledgeGraphService(db).list_topics()
    return [{"id": r.id, "key": r.topic_key, "english_name": r.english_name, "arabic_name": r.arabic_name, "parent_topic_id": r.parent_topic_id} for r in rows]

@router.get("/topics/{topic_key}")
async def get_knowledge_topic(topic_key: str, db: DbSession):
    topic, refs = await KnowledgeGraphService(db).topic_detail(topic_key)
    return {"topic": {"id": topic.id, "key": topic.topic_key, "english_name": topic.english_name, "arabic_name": topic.arabic_name, "description": topic.description}, "references": [{"id": r.id, "source_type": r.source_type, "source_entity_id": r.source_entity_id, "target_type": r.target_type, "target_entity_id": r.target_entity_id, "relationship_type": r.relationship_type, "rationale": r.rationale, "editorial_confidence": r.editorial_confidence} for r in refs]}

@router.get("/references/{entity_type}/{entity_id}")
async def get_cross_references(entity_type: str, entity_id: UUID, db: DbSession):
    rows = await KnowledgeGraphService(db).references_for(entity_type, entity_id)
    return [{"id": r.id, "source_type": r.source_type, "source_entity_id": r.source_entity_id, "target_type": r.target_type, "target_entity_id": r.target_entity_id, "relationship_type": r.relationship_type, "rationale": r.rationale, "editorial_confidence": r.editorial_confidence} for r in rows]

@router.get("/ayahs/{surah_number}/{ayah_number}")
async def tafsir_for_ayah(surah_number: int, ayah_number: int, db: DbSession, translation: str | None = None):
    rows = await KnowledgeGraphService(db).tafsir_for_ayah(surah_number, ayah_number, translation)
    return [{"id": item["entry"].id, "reference": item["entry"].canonical_reference, "arabic_text": item["entry"].arabic_text, "translation": item["translation"].translated_text if item["translation"] else None} for item in rows]

@router.get("/search")
async def search_tafsir(db: DbSession, q: str = Query(min_length=2, max_length=200), collection: str | None = None, author_id: UUID | None = None, topic: str | None = None, surah_number: int | None = Query(default=None, ge=1, le=114), limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    rows = await KnowledgeGraphService(db).search_tafsir(q, collection, author_id, topic, surah_number, limit, offset)
    return [{"id": x["entry"].id, "reference": x["entry"].canonical_reference, "arabic_text": x["entry"].arabic_text, "collection_key": x["collection"].collection_key, "collection_title": x["collection"].display_title, "author_id": x["author"].id, "author_name": x["author"].canonical_name} for x in rows]

@router.post("/admin/topics", status_code=201)
async def create_knowledge_topic(payload: KnowledgeTopicCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await KnowledgeGraphService(db).create_topic(payload); await db.commit(); return {"id": row.id, "published": row.published}

@router.post("/admin/topics/{topic_id}/aliases", status_code=201)
async def create_topic_alias(topic_id: UUID, payload: KnowledgeTopicAliasCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await KnowledgeGraphService(db).add_alias(topic_id, payload); await db.commit(); return {"id": row.id}

@router.post("/admin/cross-references", status_code=201)
async def create_cross_reference(payload: KnowledgeCrossReferenceCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await KnowledgeGraphService(db).create_cross_reference(payload); await db.commit(); return {"id": row.id, "status": row.review_status, "published": row.published}

@router.post("/admin/cross-references/{reference_id}/review")
async def review_cross_reference(reference_id: UUID, payload: KnowledgeCrossReferenceReview, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await KnowledgeGraphService(db).review_cross_reference(reference_id, admin.id, payload); await db.commit(); return {"id": row.id, "status": row.review_status, "published": row.published}

from app.services.tafsir_reader import TafsirReaderService

@router.get('/reader/{surah_number}/{ayah_number}')
async def tafsir_reader_payload(surah_number:int, ayah_number:int, db:DbSession, edition:str|None=None, translation:str|None=None):
    rows=await TafsirReaderService(db).reading_payload(surah_number,ayah_number,edition,translation)
    return [{
        'entry': {'id':x['entry'].id,'reference':x['entry'].canonical_reference,'arabic_text':x['entry'].arabic_text},
        'edition': {'id':x['edition'].id,'key':x['edition'].edition_key,'attribution':x['edition'].attribution_text},
        'collection': {'key':x['collection'].collection_key,'title':x['collection'].display_title},
        'author': {'id':x['author'].id,'name':x['author'].canonical_name,'arabic_name':x['author'].arabic_name},
        'translation': ({'text':x['translation'].translated_text,'key':x['translation_edition'].translation_key,'translator':x['translation_edition'].translator_name,'attribution':x['translation_edition'].attribution_text} if x['translation'] else None),
        'references':[{'id':r.id,'source_type':r.source_type,'source_entity_id':r.source_entity_id,'target_type':r.target_type,'target_entity_id':r.target_entity_id,'relationship_type':r.relationship_type,'rationale':r.rationale} for r in x['references']],
    } for x in rows]

@router.get('/me/bookmarks')
async def my_tafsir_bookmarks(db:DbSession,user:Annotated[User,Depends(get_current_user)]):
    return await TafsirReaderService(db).bookmarks(user.id)
@router.post('/me/bookmarks',status_code=201)
async def save_tafsir_bookmark(payload:TafsirBookmarkCreate,db:DbSession,user:Annotated[User,Depends(get_current_user)],_:Annotated[Session,Depends(require_csrf)]):
    row=await TafsirReaderService(db).save_bookmark(user.id,payload); await db.commit(); return {'id':row.id}
@router.delete('/me/bookmarks/{bookmark_id}',status_code=204)
async def delete_tafsir_bookmark(bookmark_id:UUID,db:DbSession,user:Annotated[User,Depends(get_current_user)],_:Annotated[Session,Depends(require_csrf)]):
    await TafsirReaderService(db).delete_bookmark(user.id,bookmark_id); await db.commit()

@router.get('/me/notes')
async def my_tafsir_notes(db:DbSession,user:Annotated[User,Depends(get_current_user)]): return await TafsirReaderService(db).notes(user.id)
@router.post('/me/notes',status_code=201)
async def create_tafsir_note(payload:TafsirStudyNoteCreate,db:DbSession,user:Annotated[User,Depends(get_current_user)],_:Annotated[Session,Depends(require_csrf)]):
    row=await TafsirReaderService(db).create_note(user.id,payload); await db.commit(); return {'id':row.id}
@router.delete('/me/notes/{note_id}',status_code=204)
async def delete_tafsir_note(note_id:UUID,db:DbSession,user:Annotated[User,Depends(get_current_user)],_:Annotated[Session,Depends(require_csrf)]):
    await TafsirReaderService(db).delete_note(user.id,note_id); await db.commit()

@router.get('/me/collections')
async def my_tafsir_collections(db:DbSession,user:Annotated[User,Depends(get_current_user)]): return await TafsirReaderService(db).collections(user.id)
@router.post('/me/collections',status_code=201)
async def create_tafsir_collection(payload:TafsirStudyCollectionCreate,db:DbSession,user:Annotated[User,Depends(get_current_user)],_:Annotated[Session,Depends(require_csrf)]):
    row=await TafsirReaderService(db).create_collection(user.id,payload); await db.commit(); return {'id':row.id}
@router.post('/me/collections/{collection_id}/items',status_code=201)
async def add_tafsir_collection_item(collection_id:UUID,payload:TafsirStudyCollectionItemCreate,db:DbSession,user:Annotated[User,Depends(get_current_user)],_:Annotated[Session,Depends(require_csrf)]):
    row=await TafsirReaderService(db).add_collection_item(user.id,collection_id,payload); await db.commit(); return {'id':row.id}

@router.get('/me/progress')
async def my_tafsir_progress(db:DbSession,user:Annotated[User,Depends(get_current_user)]): return await TafsirReaderService(db).progress(user.id)
@router.put('/me/progress')
async def save_tafsir_progress(payload:TafsirStudyProgressUpdate,db:DbSession,user:Annotated[User,Depends(get_current_user)],_:Annotated[Session,Depends(require_csrf)]):
    row=await TafsirReaderService(db).save_progress(user.id,payload); await db.commit(); return {'id':row.id,'status':row.status,'progress_percent':row.progress_percent}
