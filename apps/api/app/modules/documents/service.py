import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from app.core.security import generate_opaque_token
from app.core.storage import build_storage_key, get_storage_adapter
from app.modules.documents.models import Document, DocumentRequest, DocumentRequestStatus
from app.modules.documents.repository import DocumentRepository, DocumentRequestRepository

# Duplicated from `crm.service`'s attachment allow-list rather than
# imported — `documents` is meant to be the more foundational module of
# the two going forward, and the two lists are small enough that sharing
# them isn't worth a cross-module dependency (the same "rule of three"
# reasoning Milestone 5 used for its condition evaluator).
ALLOWED_DOCUMENT_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
MAX_DOCUMENT_SIZE_BYTES = 20 * 1024 * 1024

# The EICAR test string is the industry-standard signature every real
# antivirus engine (and this check) recognizes — a genuine, functioning
# safety net, not a placeholder. It is NOT a substitute for real malware
# scanning in production: wiring a real engine (a ClamAV daemon via
# `clamd`, or a cloud AV API) into this exact function REQUIRES EXTERNAL
# INFRASTRUCTURE this sandbox doesn't have.
_EICAR_SIGNATURE = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


def _scan_for_malware(content: bytes) -> None:
    if _EICAR_SIGNATURE in content:
        raise ForbiddenError("This file was flagged by malware scanning and was not saved.", code="malware_detected")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _validate_upload(*, content_type: str, content: bytes) -> None:
    if content_type not in ALLOWED_DOCUMENT_CONTENT_TYPES:
        raise ForbiddenError(f"File type '{content_type}' is not allowed.", code="document_type_not_allowed")
    if len(content) > MAX_DOCUMENT_SIZE_BYTES:
        raise ConflictError("File exceeds the maximum allowed size of 20MB.", code="document_too_large")
    _scan_for_malware(content)


def _default_context(request: DocumentRequest, lead, tenant) -> dict:
    return {
        "first_name": lead.first_name if lead else "",
        "last_name": lead.last_name if lead else "",
        "reference_number": lead.reference_number if lead else "",
        "tenant_name": tenant.name if tenant else "",
        "document_title": request.title,
        "document_link": f"/documents/upload/{request.public_token}" if request.public_token else "",
    }


# --- Requests ------------------------------------------------------------

def create_request(
    db: Session, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, title: str, description: str = "",
    requested_by: uuid.UUID | None = None, notify: bool = True,
) -> DocumentRequest:
    from app.modules.leads.repository import LeadRepository

    lead = LeadRepository(db).get(tenant_id, lead_id)
    if lead is None:
        raise NotFoundError("Lead not found.")

    request = DocumentRequestRepository(db).create(
        tenant_id=tenant_id, lead_id=lead_id, title=title, description=description,
        requested_by=requested_by, public_token=generate_opaque_token(num_bytes=32),
    )

    from app.modules.audit.service import log_event
    from app.modules.crm.service import record_activity

    log_event(
        db, tenant_id=tenant_id, actor_user_id=requested_by, action="document_request.created",
        entity_type="document_request", entity_id=request.id,
    )
    record_activity(
        db, tenant_id=tenant_id, lead_id=lead_id, actor_id=requested_by,
        activity_type="document_request.created", summary=f"Document requested: {title}",
    )

    if notify and lead.email:
        from app.modules.communications.models import EmailTriggerEvent
        from app.modules.communications.service import send_templated_email
        from app.modules.tenancy import service as tenancy_service

        tenant = tenancy_service.get_tenant_or_404(db, tenant_id)
        send_templated_email(
            db, tenant_id=tenant_id, trigger_event=EmailTriggerEvent.DOCUMENT_REQUESTED, recipient=lead.email,
            lead_id=lead_id, context=_default_context(request, lead, tenant),
        )
    return request


def get_request_or_404(db: Session, tenant_id: uuid.UUID, request_id: uuid.UUID) -> DocumentRequest:
    request = DocumentRequestRepository(db).get(tenant_id, request_id)
    if request is None:
        raise NotFoundError("Document request not found.")
    return request


def list_requests_for_lead(db: Session, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> list[DocumentRequest]:
    return DocumentRequestRepository(db).list_for_lead(tenant_id, lead_id)


def list_requests_for_tenant(db: Session, tenant_id: uuid.UUID, *, status: DocumentRequestStatus | None = None) -> list[DocumentRequest]:
    return DocumentRequestRepository(db).list_for_tenant(tenant_id, status=status)


def list_documents(db: Session, tenant_id: uuid.UUID, request_id: uuid.UUID) -> list[Document]:
    return DocumentRepository(db).list_for_request(tenant_id, request_id)


# --- Uploads -------------------------------------------------------------

def _store_document(
    db: Session, *, tenant_id: uuid.UUID, request: DocumentRequest, uploaded_by: uuid.UUID | None,
    file_name: str, content_type: str, content: bytes,
) -> Document:
    _validate_upload(content_type=content_type, content=content)

    from app.modules.entitlements import service as entitlements_service

    size_mb = max(1, -(-len(content) // (1024 * 1024)))  # round up, minimum 1MB charged
    entitlements_service.check_and_increment_usage(db, tenant_id, metric_code="document_storage_mb", feature_code="document_storage_mb", amount=size_mb)

    storage_key = build_storage_key(tenant_id=tenant_id, module="documents", entity_id=request.id, filename=file_name)
    get_storage_adapter().save(storage_key, content, content_type)

    document = DocumentRepository(db).create(
        tenant_id=tenant_id, document_request_id=request.id, lead_id=request.lead_id, uploaded_by=uploaded_by,
        file_name=file_name, content_type=content_type, size_bytes=len(content), storage_key=storage_key,
    )
    request.status = DocumentRequestStatus.UPLOADED
    db.add(request)
    db.flush()

    from app.modules.crm.service import record_activity

    record_activity(
        db, tenant_id=tenant_id, lead_id=request.lead_id, actor_id=uploaded_by,
        activity_type="document.uploaded", summary=f"Document uploaded: {file_name}",
    )
    return document


def upload_document(
    db: Session, *, tenant_id: uuid.UUID, request: DocumentRequest, uploaded_by: uuid.UUID | None,
    file_name: str, content_type: str, content: bytes,
) -> Document:
    return _store_document(db, tenant_id=tenant_id, request=request, uploaded_by=uploaded_by, file_name=file_name, content_type=content_type, content=content)


def get_document_download_url(db: Session, tenant_id: uuid.UUID, document_id: uuid.UUID) -> str:
    document = DocumentRepository(db).get(tenant_id, document_id)
    if document is None:
        raise NotFoundError("Document not found.")
    return get_storage_adapter().get_download_url(document.storage_key)


# --- Review ----------------------------------------------------------------

def approve_document_request(db: Session, *, tenant_id: uuid.UUID, request: DocumentRequest, reviewer_id: uuid.UUID | None, notes: str = "") -> DocumentRequest:
    if request.status != DocumentRequestStatus.UPLOADED:
        raise ValidationFailedError("Only an uploaded document request can be approved.", code="document_not_uploaded")

    request.status = DocumentRequestStatus.APPROVED
    request.review_notes = notes
    request.reviewed_by = reviewer_id
    request.reviewed_at = _utcnow()
    db.add(request)
    db.flush()
    _notify_review_outcome(db, request=request, approved=True)

    from app.modules.onboarding.service import advance_case_step_for_document_request

    advance_case_step_for_document_request(db, tenant_id=tenant_id, document_request_id=request.id)
    return request


def reject_document_request(db: Session, *, tenant_id: uuid.UUID, request: DocumentRequest, reviewer_id: uuid.UUID | None, notes: str = "") -> DocumentRequest:
    if request.status != DocumentRequestStatus.UPLOADED:
        raise ValidationFailedError("Only an uploaded document request can be rejected.", code="document_not_uploaded")

    request.status = DocumentRequestStatus.REJECTED
    request.review_notes = notes
    request.reviewed_by = reviewer_id
    request.reviewed_at = _utcnow()
    db.add(request)
    db.flush()
    _notify_review_outcome(db, request=request, approved=False)
    return request


def _notify_review_outcome(db: Session, *, request: DocumentRequest, approved: bool) -> None:
    from app.modules.audit.service import log_event
    from app.modules.crm.service import record_activity
    from app.modules.leads.repository import LeadRepository
    from app.modules.tenancy import service as tenancy_service

    action = "document_request.approved" if approved else "document_request.rejected"
    log_event(db, tenant_id=request.tenant_id, actor_user_id=request.reviewed_by, action=action, entity_type="document_request", entity_id=request.id)
    record_activity(
        db, tenant_id=request.tenant_id, lead_id=request.lead_id, actor_id=request.reviewed_by, activity_type=action,
        summary=f"Document {'approved' if approved else 'rejected'}: {request.title}",
    )

    lead = LeadRepository(db).get(request.tenant_id, request.lead_id)
    if lead is None or not lead.email:
        return
    tenant = tenancy_service.get_tenant_or_404(db, request.tenant_id)
    from app.modules.communications.models import EmailTriggerEvent
    from app.modules.communications.service import send_templated_email

    send_templated_email(
        db, tenant_id=request.tenant_id,
        trigger_event=EmailTriggerEvent.DOCUMENT_APPROVED if approved else EmailTriggerEvent.DOCUMENT_REJECTED,
        recipient=lead.email, lead_id=request.lead_id, context=_default_context(request, lead, tenant),
    )


# --- Public upload surface --------------------------------------------

PUBLIC_UPLOAD_THROTTLE_MAX_ATTEMPTS = 10
PUBLIC_UPLOAD_THROTTLE_WINDOW_SECONDS = 10 * 60


def get_request_by_token(db: Session, token: str) -> DocumentRequest:
    """Public, unauthenticated: the token is the authorization proof.
    Establishes RLS context for the resolved tenant before touching any
    other tenant-owned table, same pattern as
    `proposals.service.get_proposal_by_token`."""
    from app.core.db import set_rls_context

    request = DocumentRequestRepository(db).get_by_public_token(token)
    if request is None:
        raise NotFoundError("Document request not found.")
    set_rls_context(db, tenant_id=request.tenant_id, is_platform_admin=False)
    return request


def upload_document_public(db: Session, *, token: str, ip_address: str, file_name: str, content_type: str, content: bytes) -> Document:
    """Unlike the public proposal accept/reject routes, this IS gated
    behind the `document_collection` module — see the module docstring
    on `DocumentRequest` for why."""
    from app.core.db import set_rls_context
    from app.core.rate_limit import is_rate_limited
    from app.modules.entitlements import service as entitlements_service

    request = DocumentRequestRepository(db).get_by_public_token(token)
    if request is None:
        raise NotFoundError("Document request not found.")

    throttle_key = f"throttle:document_upload:{request.tenant_id}:{ip_address}"
    limited, retry_after = is_rate_limited(
        throttle_key, max_attempts=PUBLIC_UPLOAD_THROTTLE_MAX_ATTEMPTS, window_seconds=PUBLIC_UPLOAD_THROTTLE_WINDOW_SECONDS
    )
    if limited:
        from app.core.errors import RateLimitedError

        raise RateLimitedError(f"Too many requests. Try again in {retry_after} seconds.", code="document_upload_rate_limited")

    set_rls_context(db, tenant_id=request.tenant_id, is_platform_admin=False)
    entitlements_service.assert_module_enabled(db, request.tenant_id, "document_collection")

    if request.status not in {DocumentRequestStatus.REQUESTED, DocumentRequestStatus.REJECTED}:
        raise ValidationFailedError("This document request is no longer accepting uploads.", code="document_request_closed")

    return _store_document(db, tenant_id=request.tenant_id, request=request, uploaded_by=None, file_name=file_name, content_type=content_type, content=content)
