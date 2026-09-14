from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import get_current_user, require_csrf
from app.api.dependencies.platform_admin import require_platform_administrator
from app.api.dependencies.auth import DbSession
from app.models.identity import Session, User
from app.schemas.quran import QuranAyahCreate, QuranAyahView, QuranBookmarkCreate, QuranBookmarkView, QuranReadingProgressCreate, QuranReadingProgressView, QuranSurahCreate, QuranSurahReadingView, QuranSurahView, QuranTextEditionCreate, QuranTranslationEditionCreate, QuranTranslationView
from app.services.quran import QuranService

router = APIRouter(prefix="/quran", tags=["quran"])

@router.get("/surahs", response_model=list[QuranSurahView])
async def list_surahs(db: DbSession):
    return await QuranService(db).list_surahs()

@router.get("/surahs/{surah_number}", response_model=QuranSurahView)
async def get_surah(surah_number: int, db: DbSession):
    return await QuranService(db).get_surah(surah_number)


@router.get("/surahs/{surah_number}/reading", response_model=QuranSurahReadingView)
async def get_surah_reading(surah_number: int, db: DbSession, translation: str | None = None):
    return await QuranService(db).get_surah_reading(surah_number, translation)

@router.get("/me/bookmarks", response_model=list[QuranBookmarkView])
async def list_bookmarks(db: DbSession, user: Annotated[User, Depends(get_current_user)]):
    return await QuranService(db).list_bookmarks(user.id)

@router.post("/me/bookmarks", response_model=QuranBookmarkView, status_code=201)
async def add_bookmark(payload: QuranBookmarkCreate, db: DbSession, user: Annotated[User, Depends(get_current_user)], _: Annotated[Session, Depends(require_csrf)]):
    bookmark = await QuranService(db).add_bookmark(user.id, payload.ayah_id, payload.note)
    await db.commit()
    return bookmark

@router.delete("/me/bookmarks/{bookmark_id}", status_code=204)
async def remove_bookmark(bookmark_id: UUID, db: DbSession, user: Annotated[User, Depends(get_current_user)], _: Annotated[Session, Depends(require_csrf)]):
    await QuranService(db).remove_bookmark(user.id, bookmark_id)
    await db.commit()

@router.get("/me/progress", response_model=QuranReadingProgressView | None)
async def get_reading_progress(db: DbSession, user: Annotated[User, Depends(get_current_user)]):
    return await QuranService(db).get_progress(user.id)

@router.put("/me/progress", response_model=QuranReadingProgressView)
async def set_reading_progress(payload: QuranReadingProgressCreate, db: DbSession, user: Annotated[User, Depends(get_current_user)], _: Annotated[Session, Depends(require_csrf)]):
    progress = await QuranService(db).set_progress(user.id, payload.ayah_id, payload.translation_edition_id)
    await db.commit()
    return progress

@router.get("/ayahs/{reference}", response_model=QuranAyahView)
async def get_ayah(reference: str, db: DbSession):
    return await QuranService(db).get_ayah(reference)

@router.get("/translations", response_model=list[QuranTranslationView])
async def list_translations(db: DbSession):
    return await QuranService(db).list_translations()

@router.post("/admin/editions", status_code=201)
async def create_text_edition(payload: QuranTextEditionCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    edition = await QuranService(db).create_text_edition(payload)
    await db.commit()
    return {"id": edition.id, "published": edition.published}

@router.post("/admin/surahs", response_model=QuranSurahView, status_code=201)
async def create_surah(payload: QuranSurahCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    surah = await QuranService(db).create_surah(payload)
    await db.commit()
    return surah

@router.post("/admin/editions/{edition_id}/ayahs", status_code=201)
async def create_ayah(edition_id: UUID, payload: QuranAyahCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    ayah = await QuranService(db).create_ayah(edition_id, payload)
    await db.commit()
    return {"id": ayah.id, "canonical_reference": ayah.canonical_reference, "published": ayah.published}

@router.post("/admin/translations", status_code=201)
async def create_translation(payload: QuranTranslationEditionCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    translation = await QuranService(db).create_translation_edition(payload)
    await db.commit()
    return {"id": translation.id, "published": translation.published}

from app.schemas.quran import QuranImportAyahCreate, QuranImportBatchView, QuranImportManifestCreate, QuranImportReviewCreate
from app.services.quran_imports import QuranImportService

@router.post("/admin/imports", response_model=QuranImportBatchView, status_code=201)
async def create_import_batch(payload: QuranImportManifestCreate, db: DbSession, user: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    batch = await QuranImportService(db).create_batch(payload, user.id)
    await db.commit()
    return batch

@router.post("/admin/imports/{batch_id}/ayahs", status_code=201)
async def add_import_ayah(batch_id: UUID, payload: QuranImportAyahCreate, db: DbSession, user: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    item = await QuranImportService(db).add_ayah(batch_id, payload, user.id)
    await db.commit()
    return {"id": item.id, "canonical_reference": item.canonical_reference, "validation_status": item.validation_status}

@router.post("/admin/imports/{batch_id}/validate", response_model=QuranImportBatchView)
async def validate_import_batch(batch_id: UUID, db: DbSession, user: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    batch = await QuranImportService(db).validate_batch(batch_id, user.id)
    await db.commit()
    return batch

@router.post("/admin/imports/{batch_id}/review", response_model=QuranImportBatchView)
async def review_import_batch(batch_id: UUID, payload: QuranImportReviewCreate, db: DbSession, user: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    batch = await QuranImportService(db).review_batch(batch_id, user.id, payload)
    await db.commit()
    return batch

@router.post("/admin/imports/{batch_id}/publish", response_model=QuranImportBatchView)
async def publish_import_batch(batch_id: UUID, db: DbSession, user: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    batch = await QuranImportService(db).publish_batch(batch_id, user.id)
    await db.commit()
    return batch

from app.schemas.quran import (
    QuranReaderPreferenceUpdate, QuranReaderPreferenceView,
    QuranTranslationImportAyahCreate, QuranTranslationImportBatchView,
    QuranTranslationImportManifestCreate, QuranTranslationImportReviewCreate,
)
from app.services.quran_translation_imports import QuranTranslationImportService

@router.get("/me/preferences", response_model=QuranReaderPreferenceView)
async def get_reader_preferences(db: DbSession, user: Annotated[User, Depends(get_current_user)]):
    return await QuranService(db).get_preferences(user.id)

@router.put("/me/preferences", response_model=QuranReaderPreferenceView)
async def set_reader_preferences(payload: QuranReaderPreferenceUpdate, db: DbSession, user: Annotated[User, Depends(get_current_user)], _: Annotated[Session, Depends(require_csrf)]):
    preference = await QuranService(db).set_preferences(user.id, payload)
    await db.commit()
    return preference

@router.post("/admin/translation-imports", response_model=QuranTranslationImportBatchView, status_code=201)
async def create_translation_import(payload: QuranTranslationImportManifestCreate, db: DbSession, user: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    batch = await QuranTranslationImportService(db).create_batch(payload, user.id)
    await db.commit(); return batch

@router.post("/admin/translation-imports/{batch_id}/ayahs", status_code=201)
async def add_translation_import_ayah(batch_id: UUID, payload: QuranTranslationImportAyahCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    item = await QuranTranslationImportService(db).add_ayah(batch_id, payload)
    await db.commit(); return {"id": item.id, "validation_status": item.validation_status}

@router.post("/admin/translation-imports/{batch_id}/validate", response_model=QuranTranslationImportBatchView)
async def validate_translation_import(batch_id: UUID, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    batch = await QuranTranslationImportService(db).validate_batch(batch_id)
    await db.commit(); return batch

@router.post("/admin/translation-imports/{batch_id}/review", response_model=QuranTranslationImportBatchView)
async def review_translation_import(batch_id: UUID, payload: QuranTranslationImportReviewCreate, db: DbSession, user: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    batch = await QuranTranslationImportService(db).review_batch(batch_id, user.id, payload)
    await db.commit(); return batch

@router.post("/admin/translation-imports/{batch_id}/publish", response_model=QuranTranslationImportBatchView)
async def publish_translation_import(batch_id: UUID, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    batch = await QuranTranslationImportService(db).publish_batch(batch_id)
    await db.commit(); return batch

from app.schemas.quran import (
    QuranAyahAudioCreate, QuranAyahAudioView, QuranPlaybackProgressUpdate,
    QuranPlaybackProgressView, QuranRecitationEditionCreate, QuranRecitationView,
)

@router.get("/recitations", response_model=list[QuranRecitationView])
async def list_recitations(db: DbSession):
    return await QuranService(db).list_recitations()

@router.get("/surahs/{surah_number}/audio", response_model=list[QuranAyahAudioView])
async def get_surah_audio(surah_number: int, recitation: str, db: DbSession):
    return await QuranService(db).get_surah_audio(surah_number, recitation)

@router.get("/me/playback", response_model=QuranPlaybackProgressView | None)
async def get_playback_progress(db: DbSession, user: Annotated[User, Depends(get_current_user)]):
    return await QuranService(db).get_playback_progress(user.id)

@router.put("/me/playback", response_model=QuranPlaybackProgressView)
async def set_playback_progress(payload: QuranPlaybackProgressUpdate, db: DbSession, user: Annotated[User, Depends(get_current_user)], _: Annotated[Session, Depends(require_csrf)]):
    progress = await QuranService(db).set_playback_progress(user.id, payload)
    await db.commit()
    return progress

@router.post("/admin/recitations", status_code=201)
async def create_recitation(payload: QuranRecitationEditionCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    recitation = await QuranService(db).create_recitation_edition(payload)
    await db.commit()
    return {"id": recitation.id, "published": recitation.published}

@router.post("/admin/recitations/{recitation_id}/ayahs", status_code=201)
async def add_recitation_audio(recitation_id: UUID, payload: QuranAyahAudioCreate, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    audio = await QuranService(db).add_ayah_audio(recitation_id, payload)
    await db.commit()
    return {"id": audio.id, "published": audio.published}

@router.post("/admin/recitations/{recitation_id}/publish")
async def publish_recitation(recitation_id: UUID, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    recitation = await QuranService(db).publish_recitation(recitation_id)
    await db.commit()
    return {"id": recitation.id, "published": recitation.published}
