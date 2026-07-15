import uuid

from fastapi import APIRouter, Depends, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.db import get_db
from app.dependencies.entitlements import require_module
from app.dependencies.permissions import require_permission
from app.modules.documents import service as documents_service
from app.modules.documents.models import DocumentRequestStatus
from app.modules.documents.schemas import CreateDocumentRequestRequest, ReviewDocumentRequestRequest

public_router = APIRouter(prefix="/public/documents", tags=["public-documents"])
router = APIRouter(prefix="/tenant/document-requests", tags=["document-requests"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _request_to_dict(request) -> dict:
    return {
        "id": str(request.id), "lead_id": str(request.lead_id), "title": request.title, "description": request.description,
        "status": request.status.value, "public_token": request.public_token,
        "review_notes": request.review_notes, "reviewed_by": str(request.reviewed_by) if request.reviewed_by else None,
        "reviewed_at": request.reviewed_at.isoformat() if request.reviewed_at else None,
        "created_at": request.created_at.isoformat(),
    }


def _document_to_dict(document) -> dict:
    return {
        "id": str(document.id), "file_name": document.file_name, "content_type": document.content_type,
        "size_bytes": document.size_bytes, "uploaded_by": str(document.uploaded_by) if document.uploaded_by else None,
        "created_at": document.created_at.isoformat(),
    }


# --- Tenant document requests -------------------------------------------

@router.get("")
def list_document_requests(
    lead_id: uuid.UUID | None = None, status: DocumentRequestStatus | None = None,
    ctx: TenantContext = Depends(require_permission("documents.view")),
    _mod: TenantContext = Depends(require_module("document_collection")), db: Session = Depends(get_db),
) -> list[dict]:
    requests = (
        documents_service.list_requests_for_lead(db, ctx.tenant_id, lead_id) if lead_id
        else documents_service.list_requests_for_tenant(db, ctx.tenant_id, status=status)
    )
    return [_request_to_dict(r) for r in requests]


@router.post("", status_code=201)
def create_document_request(
    payload: CreateDocumentRequestRequest, ctx: TenantContext = Depends(require_permission("documents.manage")),
    _mod: TenantContext = Depends(require_module("document_collection")), db: Session = Depends(get_db),
) -> dict:
    request = documents_service.create_request(
        db, tenant_id=ctx.tenant_id, lead_id=payload.lead_id, title=payload.title, description=payload.description,
        requested_by=ctx.user_id, notify=payload.notify,
    )
    return _request_to_dict(request)


@router.get("/{request_id}")
def get_document_request(
    request_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("documents.view")),
    _mod: TenantContext = Depends(require_module("document_collection")), db: Session = Depends(get_db),
) -> dict:
    request = documents_service.get_request_or_404(db, ctx.tenant_id, request_id)
    return _request_to_dict(request)


@router.get("/{request_id}/documents")
def list_documents(
    request_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("documents.view")),
    _mod: TenantContext = Depends(require_module("document_collection")), db: Session = Depends(get_db),
) -> list[dict]:
    return [_document_to_dict(d) for d in documents_service.list_documents(db, ctx.tenant_id, request_id)]


@router.post("/{request_id}/documents", status_code=201)
async def upload_document(
    request_id: uuid.UUID, file: UploadFile, ctx: TenantContext = Depends(require_permission("documents.upload")),
    _mod: TenantContext = Depends(require_module("document_collection")), db: Session = Depends(get_db),
) -> dict:
    request = documents_service.get_request_or_404(db, ctx.tenant_id, request_id)
    content = await file.read()
    document = documents_service.upload_document(
        db, tenant_id=ctx.tenant_id, request=request, uploaded_by=ctx.user_id,
        file_name=file.filename or "upload", content_type=file.content_type or "application/octet-stream", content=content,
    )
    return _document_to_dict(document)


@router.get("/{request_id}/documents/{document_id}/download-url")
def get_document_download_url(
    request_id: uuid.UUID, document_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("documents.view")),
    _mod: TenantContext = Depends(require_module("document_collection")), db: Session = Depends(get_db),
) -> dict:
    url = documents_service.get_document_download_url(db, ctx.tenant_id, document_id)
    return {"url": url}


@router.post("/{request_id}/approve")
def approve_document_request(
    request_id: uuid.UUID, payload: ReviewDocumentRequestRequest, ctx: TenantContext = Depends(require_permission("documents.approve")),
    _mod: TenantContext = Depends(require_module("document_collection")), db: Session = Depends(get_db),
) -> dict:
    request = documents_service.get_request_or_404(db, ctx.tenant_id, request_id)
    request = documents_service.approve_document_request(db, tenant_id=ctx.tenant_id, request=request, reviewer_id=ctx.user_id, notes=payload.notes)
    return _request_to_dict(request)


@router.post("/{request_id}/reject")
def reject_document_request(
    request_id: uuid.UUID, payload: ReviewDocumentRequestRequest, ctx: TenantContext = Depends(require_permission("documents.approve")),
    _mod: TenantContext = Depends(require_module("document_collection")), db: Session = Depends(get_db),
) -> dict:
    request = documents_service.get_request_or_404(db, ctx.tenant_id, request_id)
    request = documents_service.reject_document_request(db, tenant_id=ctx.tenant_id, request=request, reviewer_id=ctx.user_id, notes=payload.notes)
    return _request_to_dict(request)


# --- Public upload surface -------------------------------------------

@public_router.get("/{token}")
def public_get_document_request(token: str, db: Session = Depends(get_db)) -> dict:
    request = documents_service.get_request_by_token(db, token)
    return {
        "title": request.title, "description": request.description, "status": request.status.value,
    }


@public_router.post("/{token}/upload", status_code=201)
async def public_upload_document(token: str, file: UploadFile, request: Request, db: Session = Depends(get_db)) -> dict:
    content = await file.read()
    document = documents_service.upload_document_public(
        db, token=token, ip_address=_client_ip(request), file_name=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream", content=content,
    )
    return {"status": "received", "document_id": str(document.id)}
