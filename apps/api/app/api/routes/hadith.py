from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends

from app.api.dependencies.auth import get_current_user, require_csrf
from app.api.dependencies.platform_admin import require_platform_administrator
from app.api.dependencies.auth import DbSession
from app.models.identity import Session, User
from app.schemas.hadith import *
from app.services.hadith import HadithService
from app.services.hadith_imports import HadithImportService

router = APIRouter(prefix="/hadith", tags=["hadith"])

@router.get("/collections", response_model=list[HadithCollectionView])
async def list_collections(db: DbSession): return await HadithService(db).list_collections()

@router.get("/narrations/{reference}", response_model=HadithNarrationView)
async def get_narration(reference: str, db: DbSession): return await HadithService(db).get_narration(reference)

@router.post("/admin/collections", status_code=201)
async def create_collection(payload: HadithCollectionCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await HadithService(db).create_collection(payload); await db.commit(); return {"id": row.id, "published": row.published}

@router.post("/admin/collections/{collection_id}/books", status_code=201)
async def create_book(collection_id: UUID, payload: HadithBookCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await HadithService(db).create_book(collection_id, payload); await db.commit(); return {"id": row.id, "published": row.published}

@router.post("/admin/books/{book_id}/chapters", status_code=201)
async def create_chapter(book_id: UUID, payload: HadithChapterCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await HadithService(db).create_chapter(book_id, payload); await db.commit(); return {"id": row.id, "published": row.published}

@router.post("/admin/collections/{collection_id}/narrations", status_code=201)
async def create_narration(collection_id: UUID, payload: HadithNarrationCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await HadithService(db).create_narration(collection_id, payload); await db.commit(); return {"id": row.id, "canonical_reference": row.canonical_reference, "published": row.published}

@router.post("/admin/narrators", status_code=201)
async def create_narrator(payload: HadithNarratorCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await HadithService(db).create_narrator(payload); await db.commit(); return {"id": row.id}

@router.post("/admin/narrations/{narration_id}/isnad", status_code=201)
async def add_isnad(narration_id: UUID, payload: HadithIsnadNodeCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await HadithService(db).add_isnad_node(narration_id, payload); await db.commit(); return {"id": row.id, "position": row.position}

@router.post("/admin/narrations/{narration_id}/gradings", status_code=201)
async def add_grading(narration_id: UUID, payload: HadithGradingCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await HadithService(db).add_grading(narration_id, payload); await db.commit(); return {"id": row.id, "published": row.published}


@router.post("/admin/imports", response_model=HadithImportBatchView, status_code=201)
async def create_import(payload: HadithImportManifestCreate, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    row = await HadithImportService(db).create_batch(payload, admin.id); await db.commit(); return row

@router.post("/admin/imports/{batch_id}/narrations", status_code=201)
async def stage_import_narration(batch_id: UUID, payload: HadithImportNarrationCreate, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    row = await HadithImportService(db).add_narration(batch_id, payload, admin.id); await db.commit(); return {"id": row.id, "canonical_reference": row.canonical_reference, "validation_status": row.validation_status}

@router.post("/admin/import-narrations/{import_narration_id}/isnad", status_code=201)
async def stage_import_isnad(import_narration_id: UUID, payload: HadithImportIsnadNodeCreate, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    row = await HadithImportService(db).add_isnad_node(import_narration_id, payload, admin.id); await db.commit(); return {"id": row.id, "position": row.position}

@router.post("/admin/duplicate-candidates/{candidate_id}/resolve")
async def resolve_duplicate(candidate_id: UUID, payload: HadithDuplicateResolutionCreate, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    row = await HadithImportService(db).resolve_duplicate(candidate_id, payload, admin.id); await db.commit(); return {"id": row.id, "resolution": row.resolution}

@router.post("/admin/imports/{batch_id}/validate", response_model=HadithImportBatchView)
async def validate_import(batch_id: UUID, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    row = await HadithImportService(db).validate_batch(batch_id, admin.id); await db.commit(); return row

@router.post("/admin/imports/{batch_id}/review-assignments", status_code=201)
async def assign_import_reviewer(batch_id: UUID, payload: HadithImportReviewAssignmentCreate, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    row = await HadithImportService(db).assign_reviewer(batch_id, payload, admin.id); await db.commit(); return {"id": row.id, "review_domain": row.review_domain, "status": row.status}

@router.get("/me/review-queue")
async def hadith_review_queue(db: DbSession, user: Annotated[User, Depends(get_current_user)]):
    return await HadithImportService(db).reviewer_queue(user.id)

@router.post("/me/review-assignments/{assignment_id}/decision", response_model=HadithImportBatchView)
async def decide_import_review(assignment_id: UUID, payload: HadithImportReviewCreate, db: DbSession, user: Annotated[User, Depends(get_current_user)], _: Annotated[Session, Depends(require_csrf)]):
    row = await HadithImportService(db).review_assignment(assignment_id, user.id, payload); await db.commit(); return row

@router.post("/admin/imports/{batch_id}/publish", response_model=HadithImportBatchView)
async def publish_import(batch_id: UUID, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    row = await HadithImportService(db).publish_batch(batch_id, admin.id); await db.commit(); return row

from app.services.hadith_governance import HadithGovernanceService, HadithReadingService

@router.get("/collections/{collection_key}/books", response_model=list[HadithBookView])
async def list_hadith_books(collection_key: str, db: DbSession):
    return await HadithReadingService(db).list_books(collection_key)

@router.get("/collections/{collection_key}/books/{book_number}/chapters", response_model=list[HadithChapterView])
async def list_hadith_chapters(collection_key: str, book_number: int, db: DbSession):
    return await HadithReadingService(db).list_chapters(collection_key, book_number)

@router.get("/collections/{collection_key}/books/{book_number}/chapters/{chapter_number}", response_model=HadithChapterReadingView)
async def read_hadith_chapter(collection_key: str, book_number: int, chapter_number: int, db: DbSession, translation: str | None = None):
    return await HadithReadingService(db).chapter_reading(collection_key, book_number, chapter_number, translation)

@router.post("/admin/translation-editions", status_code=201)
async def create_hadith_translation_edition(payload: HadithTranslationEditionCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await HadithGovernanceService(db).create_translation_edition(payload); await db.commit(); return {"id": row.id, "published": row.published}

@router.post("/admin/translation-imports", status_code=201)
async def create_hadith_translation_import(payload: HadithTranslationImportManifestCreate, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    row = await HadithGovernanceService(db).create_translation_batch(payload, admin.id); await db.commit(); return {"id": row.id, "status": row.status}

@router.post("/admin/translation-imports/{batch_id}/items", status_code=201)
async def add_hadith_translation_item(batch_id: UUID, payload: HadithTranslationImportItemCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await HadithGovernanceService(db).add_translation_item(batch_id, payload); await db.commit(); return {"id": row.id, "validation_status": row.validation_status}

@router.post("/admin/translation-imports/{batch_id}/validate")
async def validate_hadith_translation_import(batch_id: UUID, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await HadithGovernanceService(db).validate_translation_batch(batch_id); await db.commit(); return {"id": row.id, "status": row.status, "validation_summary": row.validation_summary}

@router.post("/admin/translation-imports/{batch_id}/review")
async def review_hadith_translation_import(batch_id: UUID, payload: HadithGovernedReviewCreate, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    row = await HadithGovernanceService(db).review_translation_batch(batch_id, admin.id, payload); await db.commit(); return {"id": row.id, "status": row.status}

@router.post("/admin/translation-imports/{batch_id}/publish")
async def publish_hadith_translation_import(batch_id: UUID, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await HadithGovernanceService(db).publish_translation_batch(batch_id); await db.commit(); return {"id": row.id, "status": row.status}

@router.post("/admin/grading-imports", status_code=201)
async def create_hadith_grading_import(payload: HadithGradingImportManifestCreate, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    row = await HadithGovernanceService(db).create_grading_batch(payload, admin.id); await db.commit(); return {"id": row.id, "status": row.status}

@router.post("/admin/grading-imports/{batch_id}/items", status_code=201)
async def add_hadith_grading_item(batch_id: UUID, payload: HadithGradingImportItemCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await HadithGovernanceService(db).add_grading_item(batch_id, payload); await db.commit(); return {"id": row.id, "validation_status": row.validation_status}

@router.post("/admin/grading-imports/{batch_id}/validate")
async def validate_hadith_grading_import(batch_id: UUID, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await HadithGovernanceService(db).validate_grading_batch(batch_id); await db.commit(); return {"id": row.id, "status": row.status, "validation_summary": row.validation_summary}

@router.post("/admin/grading-imports/{batch_id}/review")
async def review_hadith_grading_import(batch_id: UUID, payload: HadithGovernedReviewCreate, db: DbSession, admin: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    row = await HadithGovernanceService(db).review_grading_batch(batch_id, admin.id, payload); await db.commit(); return {"id": row.id, "status": row.status}

@router.post("/admin/grading-imports/{batch_id}/publish")
async def publish_hadith_grading_import(batch_id: UUID, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    row = await HadithGovernanceService(db).publish_grading_batch(batch_id); await db.commit(); return {"id": row.id, "status": row.status}

from app.services.hadith_reader_tools import HadithReaderToolsService

@router.get("/search", response_model=list[HadithSearchResultView])
async def search_hadith(db: DbSession, q: str | None = None, collection: str | None = None, grader: str | None = None, grading: str | None = None, narrator: str | None = None, limit: int = 50, offset: int = 0):
    limit = min(max(limit, 1), 100); offset = max(offset, 0)
    return await HadithReaderToolsService(db).search(q, collection, grader, grading, narrator, limit, offset)

@router.get("/narrations/{narration_id}/isnad", response_model=list[HadithIsnadNodeView])
async def hadith_isnad(narration_id: UUID, db: DbSession):
    return await HadithReaderToolsService(db).isnad(narration_id)

@router.get("/narrators/{narrator_id}", response_model=HadithNarratorProfileView)
async def hadith_narrator_profile(narrator_id: UUID, db: DbSession):
    return await HadithReaderToolsService(db).narrator_profile(narrator_id)

@router.get("/me/bookmarks", response_model=list[HadithBookmarkView])
async def hadith_bookmarks(db: DbSession, user: Annotated[User, Depends(get_current_user)]):
    return await HadithReaderToolsService(db).list_bookmarks(user.id)

@router.post("/me/bookmarks", response_model=HadithBookmarkView)
async def save_hadith_bookmark(payload: HadithBookmarkCreate, db: DbSession, user: Annotated[User, Depends(get_current_user)], _: Annotated[Session, Depends(require_csrf)]):
    row = await HadithReaderToolsService(db).save_bookmark(user.id, payload.narration_id, payload.note); await db.commit(); return row

@router.delete("/me/bookmarks/{bookmark_id}", status_code=204)
async def remove_hadith_bookmark(bookmark_id: UUID, db: DbSession, user: Annotated[User, Depends(get_current_user)], _: Annotated[Session, Depends(require_csrf)]):
    await HadithReaderToolsService(db).delete_bookmark(user.id, bookmark_id); await db.commit()

@router.get("/me/history", response_model=list[HadithHistoryView])
async def hadith_history(db: DbSession, user: Annotated[User, Depends(get_current_user)], limit: int = 50):
    return await HadithReaderToolsService(db).history(user.id, min(max(limit, 1), 100))

@router.post("/me/history", response_model=HadithHistoryView)
async def record_hadith_history(payload: HadithHistoryCreate, db: DbSession, user: Annotated[User, Depends(get_current_user)], _: Annotated[Session, Depends(require_csrf)]):
    row = await HadithReaderToolsService(db).record_history(user.id, payload.narration_id); await db.commit(); return row

@router.post("/me/citation-exports")
async def export_hadith_citation(payload: HadithCitationExportCreate, db: DbSession, user: Annotated[User, Depends(get_current_user)], _: Annotated[Session, Depends(require_csrf)]):
    row = await HadithReaderToolsService(db).citation_export(user.id, payload.narration_id, payload.format); await db.commit(); return row
