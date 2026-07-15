import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.documents.models import Document, DocumentRequest


class DocumentRequestRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, request_id: uuid.UUID) -> DocumentRequest | None:
        return self.db.execute(
            select(DocumentRequest).where(DocumentRequest.tenant_id == tenant_id, DocumentRequest.id == request_id)
        ).scalar_one_or_none()

    def get_by_public_token(self, token: str) -> DocumentRequest | None:
        """Deliberately not tenant-scoped — same reasoning as
        `ProposalRepository.get_by_public_token`: the token itself is the
        authorization proof for the public upload page."""
        return self.db.execute(select(DocumentRequest).where(DocumentRequest.public_token == token)).scalar_one_or_none()

    def list_for_lead(self, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> list[DocumentRequest]:
        return list(
            self.db.execute(
                select(DocumentRequest)
                .where(DocumentRequest.tenant_id == tenant_id, DocumentRequest.lead_id == lead_id)
                .order_by(DocumentRequest.created_at.desc())
            )
            .scalars()
            .all()
        )

    def list_for_tenant(self, tenant_id: uuid.UUID, *, status=None) -> list[DocumentRequest]:
        stmt = select(DocumentRequest).where(DocumentRequest.tenant_id == tenant_id)
        if status is not None:
            stmt = stmt.where(DocumentRequest.status == status)
        return list(self.db.execute(stmt.order_by(DocumentRequest.created_at.desc())).scalars().all())

    def create(self, **fields) -> DocumentRequest:
        request = DocumentRequest(**fields)
        self.db.add(request)
        self.db.flush()
        return request


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, document_id: uuid.UUID) -> Document | None:
        return self.db.execute(
            select(Document).where(Document.tenant_id == tenant_id, Document.id == document_id)
        ).scalar_one_or_none()

    def list_for_request(self, tenant_id: uuid.UUID, document_request_id: uuid.UUID) -> list[Document]:
        return list(
            self.db.execute(
                select(Document)
                .where(Document.tenant_id == tenant_id, Document.document_request_id == document_request_id)
                .order_by(Document.created_at.desc())
            )
            .scalars()
            .all()
        )

    def create(
        self, *, tenant_id: uuid.UUID, document_request_id: uuid.UUID, lead_id: uuid.UUID, uploaded_by,
        file_name: str, content_type: str, size_bytes: int, storage_key: str,
    ) -> Document:
        document = Document(
            tenant_id=tenant_id, document_request_id=document_request_id, lead_id=lead_id, uploaded_by=uploaded_by,
            file_name=file_name, content_type=content_type, size_bytes=size_bytes, storage_key=storage_key,
        )
        self.db.add(document)
        self.db.flush()
        return document
