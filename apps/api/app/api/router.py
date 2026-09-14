from app.api.routes import knowledge_network, ai_orchestration, multilingual_ai, personalization_ai, ai_quality, deployment
from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.organisations import router as organisations_router
from app.api.routes.sources import router as sources_router
from app.api.routes.quran import router as quran_router
from app.api.routes.hadith import router as hadith_router
from app.api.routes.tafsir import router as tafsir_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.assistant import router as assistant_router
from app.api.routes.learning import router as learning_router
from app.api.routes.research import router as research_router
from app.api.routes.community import router as community_router
from app.api.routes.scholarly import router as scholarly_router
from app.api.routes.ai_provider import router as ai_provider_router

router = APIRouter()
router.include_router(ai_provider_router)
router.include_router(auth_router)
router.include_router(organisations_router)
router.include_router(sources_router)
router.include_router(quran_router)
router.include_router(hadith_router)
router.include_router(tafsir_router)
router.include_router(retrieval_router)
router.include_router(assistant_router)
router.include_router(learning_router)
router.include_router(research_router)
router.include_router(community_router)
router.include_router(scholarly_router)

router.include_router(knowledge_network.router)
router.include_router(ai_orchestration.router)
router.include_router(multilingual_ai.router)

router.include_router(personalization_ai.router)

router.include_router(ai_quality.router)

router.include_router(deployment.router)

from app.api.routes import operations
router.include_router(operations.router)
from app.api.routes import compliance
router.include_router(compliance.router)
from app.api.routes import launch_governance
router.include_router(launch_governance.router)
from app.api.routes import developer_platform
router.include_router(developer_platform.router)
from app.api.routes import institutional_network
router.include_router(institutional_network.router)
from app.api.routes import civilizational_infrastructure
router.include_router(civilizational_infrastructure.router)
from app.api.routes import living_civilization
router.include_router(living_civilization.router)
from app.api.routes import ummah_services
router.include_router(ummah_services.router)
from app.api.routes import global_ummah_network
router.include_router(global_ummah_network.router)
from app.api.routes import civilization_os
router.include_router(civilization_os.router)
from app.api.routes import islamic_life
router.include_router(islamic_life.router)
from app.api.routes import platform_v1
router.include_router(platform_v1.router)
