import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import DbSession, get_current_user, require_csrf
from app.api.dependencies.platform_admin import require_platform_administrator
from app.infrastructure.source_integrity import calculate_object_digest
from app.models.identity import Session, User
from app.schemas.sources import (
    AcquisitionCreate, AttributionUpsert, AuthorityUpdate, EditionCreate, EditionView,
    IngestionTransition, IntegrityVerifyRequest, LegalReviewUpdate, LicenceCreate,
    PassageCreate, PassageView, ReviewAssignmentCreate, ReviewDecisionCreate, SourceCreate,
    SourceView,
)
from app.services.sources import SourceRegistryService

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceView])
async def list_public_sources(db: DbSession):
    return await SourceRegistryService(db).list_public_sources()


@router.post("/admin/licences", status_code=201)
async def create_licence(
    payload: LicenceCreate,
    db: DbSession,
    _: Annotated[User, Depends(require_platform_administrator)],
    __: Annotated[Session, Depends(require_csrf)],
):
    licence = await SourceRegistryService(db).create_licence(payload)
    await db.commit()
    return {"id": licence.id, "legal_review_status": licence.legal_review_status}


@router.post("/admin", response_model=SourceView, status_code=201)
async def create_source(
    payload: SourceCreate,
    db: DbSession,
    _: Annotated[User, Depends(require_platform_administrator)],
    __: Annotated[Session, Depends(require_csrf)],
):
    source = await SourceRegistryService(db).create_source(payload)
    await db.commit()
    return source


@router.post("/admin/{source_id}/editions", response_model=EditionView, status_code=201)
async def create_edition(
    source_id: UUID,
    payload: EditionCreate,
    db: DbSession,
    _: Annotated[User, Depends(require_platform_administrator)],
    __: Annotated[Session, Depends(require_csrf)],
):
    edition = await SourceRegistryService(db).create_edition(source_id, payload)
    await db.commit()
    return edition


@router.post("/admin/editions/{edition_id}/acquisitions", status_code=201)
async def record_acquisition(
    edition_id: UUID,
    payload: AcquisitionCreate,
    db: DbSession,
    actor: Annotated[User, Depends(require_platform_administrator)],
    _: Annotated[Session, Depends(require_csrf)],
):
    acquisition = await SourceRegistryService(db).record_acquisition(edition_id, payload, actor)
    await db.commit()
    return {"id": acquisition.id, "edition_id": acquisition.edition_id}


@router.patch("/admin/licences/{licence_id}/legal-review")
async def update_licence_legal_review(
    licence_id: UUID,
    payload: LegalReviewUpdate,
    db: DbSession,
    _: Annotated[User, Depends(require_platform_administrator)],
    __: Annotated[Session, Depends(require_csrf)],
):
    licence = await SourceRegistryService(db).update_licence_legal_review(licence_id, payload.decision)
    await db.commit()
    return {"id": licence.id, "legal_review_status": licence.legal_review_status}


@router.patch("/admin/{source_id}/authority")
async def update_source_authority(
    source_id: UUID,
    payload: AuthorityUpdate,
    db: DbSession,
    _: Annotated[User, Depends(require_platform_administrator)],
    __: Annotated[Session, Depends(require_csrf)],
):
    source = await SourceRegistryService(db).update_source_authority(source_id, payload.status)
    await db.commit()
    return {"id": source.id, "authority_status": source.authority_status}


@router.patch("/admin/editions/{edition_id}/ingestion", response_model=EditionView)
async def transition_ingestion(
    edition_id: UUID,
    payload: IngestionTransition,
    db: DbSession,
    actor: Annotated[User, Depends(require_platform_administrator)],
    _: Annotated[Session, Depends(require_csrf)],
):
    edition = await SourceRegistryService(db).transition_ingestion(edition_id, payload, actor)
    await db.commit()
    return edition


@router.post("/admin/editions/{edition_id}/integrity", status_code=201)
async def verify_integrity(
    edition_id: UUID,
    payload: IntegrityVerifyRequest,
    db: DbSession,
    actor: Annotated[User, Depends(require_platform_administrator)],
    _: Annotated[Session, Depends(require_csrf)],
):
    digest = await asyncio.to_thread(calculate_object_digest, payload.object_key, payload.algorithm)
    record = await SourceRegistryService(db).verify_integrity(
        edition_id, payload.object_key, payload.algorithm, actor, digest.digest, digest.byte_size
    )
    await db.commit()
    return {"id": record.id, "digest": record.digest, "byte_size": record.byte_size, "verified": True}


@router.post("/admin/editions/{edition_id}/review-assignments", status_code=201)
async def assign_review(
    edition_id: UUID,
    payload: ReviewAssignmentCreate,
    db: DbSession,
    actor: Annotated[User, Depends(require_platform_administrator)],
    _: Annotated[Session, Depends(require_csrf)],
):
    assignment = await SourceRegistryService(db).assign_review(edition_id, payload, actor)
    await db.commit()
    return {"id": assignment.id, "status": assignment.status}


@router.post("/review-assignments/{assignment_id}/decision", status_code=201)
async def submit_review(
    assignment_id: UUID,
    payload: ReviewDecisionCreate,
    db: DbSession,
    actor: Annotated[User, Depends(get_current_user)],
    _: Annotated[Session, Depends(require_csrf)],
):
    review = await SourceRegistryService(db).submit_review(assignment_id, payload, actor)
    await db.commit()
    return {"id": review.id, "decision": review.decision}


@router.post("/admin/editions/{edition_id}/passages", response_model=PassageView, status_code=201)
async def create_passage(
    edition_id: UUID,
    payload: PassageCreate,
    db: DbSession,
    actor: Annotated[User, Depends(require_platform_administrator)],
    _: Annotated[Session, Depends(require_csrf)],
):
    passage = await SourceRegistryService(db).create_passage(edition_id, payload, actor)
    await db.commit()
    return passage


@router.put("/admin/editions/{edition_id}/attributions", status_code=200)
async def upsert_attribution(
    edition_id: UUID,
    payload: AttributionUpsert,
    db: DbSession,
    _: Annotated[User, Depends(require_platform_administrator)],
    __: Annotated[Session, Depends(require_csrf)],
):
    attribution = await SourceRegistryService(db).upsert_attribution(edition_id, payload)
    await db.commit()
    return {"id": attribution.id, "language": attribution.language}


@router.post("/admin/editions/{edition_id}/evaluate-retrieval")
async def evaluate_retrieval(
    edition_id: UUID,
    db: DbSession,
    actor: Annotated[User, Depends(require_platform_administrator)],
    _: Annotated[Session, Depends(require_csrf)],
):
    result = await SourceRegistryService(db).evaluate_retrieval(edition_id, actor)
    await db.commit()
    return {"eligible": result.eligible, "failed_gates": result.failed_gates()}


@router.get("/editions/{edition_id}/passages", response_model=list[PassageView])
async def list_public_passages(edition_id: UUID, db: DbSession):
    return await SourceRegistryService(db).list_public_passages(edition_id)

# Claim-level provenance and registry governance
from app.schemas.sources import ApprovalPolicyCreate, ClaimPassageLinkCreate, PassageCorrectionCreate, PassageCorrectionDecision, SourceClaimCreate, SupersessionCreate
from app.services.source_provenance import SourceProvenanceService


@router.post("/admin/claims", status_code=201)
async def create_source_claim(payload: SourceClaimCreate, db: DbSession, actor: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    claim = await SourceProvenanceService(db).create_claim(payload, actor)
    await db.commit()
    return {"id": claim.id, "claim_status": claim.claim_status}


@router.post("/admin/claims/{claim_id}/passages", status_code=201)
async def link_claim_passage(claim_id: UUID, payload: ClaimPassageLinkCreate, db: DbSession, actor: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    link = await SourceProvenanceService(db).link_passage(claim_id, payload, actor)
    await db.commit()
    return {"id": link.id, "relation_type": link.relation_type}


@router.post("/admin/passages/{passage_id}/corrections", status_code=201)
async def request_passage_correction(passage_id: UUID, payload: PassageCorrectionCreate, db: DbSession, actor: Annotated[User, Depends(get_current_user)], _: Annotated[Session, Depends(require_csrf)]):
    correction = await SourceProvenanceService(db).request_correction(passage_id, payload.reason, actor)
    await db.commit()
    return {"id": correction.id, "status": correction.status}


@router.post("/admin/corrections/{correction_id}/decision")
async def decide_passage_correction(correction_id: UUID, payload: PassageCorrectionDecision, db: DbSession, actor: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    correction = await SourceProvenanceService(db).decide_correction(correction_id, payload, actor)
    await db.commit()
    return {"id": correction.id, "status": correction.status}


@router.post("/admin/editions/{edition_id}/supersede", status_code=201)
async def supersede_edition(edition_id: UUID, payload: SupersessionCreate, db: DbSession, actor: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    record = await SourceProvenanceService(db).supersede_edition(edition_id, payload, actor)
    await db.commit()
    return {"id": record.id, "replacement_edition_id": record.replacement_edition_id}


@router.post("/admin/approval-policies", status_code=201)
async def create_approval_policy(payload: ApprovalPolicyCreate, db: DbSession, actor: Annotated[User, Depends(require_platform_administrator)], _: Annotated[Session, Depends(require_csrf)]):
    policy = await SourceProvenanceService(db).create_policy(payload, actor)
    await db.commit()
    return {"id": policy.id, "status": policy.status}


@router.post("/admin/approval-policies/{policy_id}/activate")
async def activate_approval_policy(policy_id: UUID, db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], __: Annotated[Session, Depends(require_csrf)]):
    policy = await SourceProvenanceService(db).activate_policy(policy_id)
    await db.commit()
    return {"id": policy.id, "status": policy.status}

# Reviewer queues, provenance inspection, registry administration, and audit exports
from fastapi.responses import Response
from app.schemas.sources import (
    AuditExportRequest, ProvenanceClaimView, RegistryDashboardView, ReviewerQueueItem,
)
from app.services.source_registry_admin import SourceRegistryAdminService


@router.get("/reviewer/queue", response_model=list[ReviewerQueueItem])
async def reviewer_queue(
    db: DbSession,
    actor: Annotated[User, Depends(get_current_user)],
):
    return await SourceRegistryAdminService(db).reviewer_queue(actor)


@router.get("/admin/dashboard", response_model=RegistryDashboardView)
async def registry_dashboard(
    db: DbSession,
    _: Annotated[User, Depends(require_platform_administrator)],
):
    return await SourceRegistryAdminService(db).dashboard()


@router.get("/admin/claims/{claim_id}/provenance", response_model=ProvenanceClaimView)
async def inspect_claim_provenance(
    claim_id: UUID,
    db: DbSession,
    _: Annotated[User, Depends(require_platform_administrator)],
):
    return await SourceRegistryAdminService(db).provenance_view(claim_id)


@router.post("/admin/audit-exports")
async def export_source_audit(
    payload: AuditExportRequest,
    db: DbSession,
    actor: Annotated[User, Depends(require_platform_administrator)],
    _: Annotated[Session, Depends(require_csrf)],
):
    content, media_type = await SourceRegistryAdminService(db).export_audit(
        actor, payload.edition_id, payload.format
    )
    await db.commit()
    extension = "json" if payload.format == "json" else "csv"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="source-audit.{extension}"',
            "X-Content-SHA256": __import__("hashlib").sha256(content).hexdigest(),
        },
    )
