from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.deps import client_ip
from app.db.session import get_db
from app.schemas.public_enquiry import (
    PublicEnquirySubmitRequest,
    PublicEnquirySubmitResponse,
    PublicFormConfigOut,
    PublicServiceOut,
)
from app.schemas.qualification import QualificationQuestionOut
from app.services.lead_service import AnswerInput
from app.services.public_enquiry_service import PublicEnquiryService

router = APIRouter(prefix="/public/{public_key}", tags=["public-enquiry"])


@router.get("/form", response_model=PublicFormConfigOut)
def get_form_config(public_key: uuid.UUID, db: Session = Depends(get_db)) -> PublicFormConfigOut:
    config = PublicEnquiryService(db).get_form_config(public_key)
    settings = config.tenant.settings
    return PublicFormConfigOut(
        tenant_name=config.tenant.name,
        brand_primary_color=settings.brand_primary_color if settings else "#F97316",
        brand_secondary_color=settings.brand_secondary_color if settings else "#111827",
        logo_url=settings.logo_url if settings else None,
        services=[PublicServiceOut.model_validate(s) for s in config.services],
        questions=[
            QualificationQuestionOut.model_validate(q)
            for q in (config.form.questions if config.form else [])
            if q.is_active
        ],
        privacy_text=config.privacy_text,
    )


@router.post("/submit", response_model=PublicEnquirySubmitResponse)
def submit_enquiry(
    public_key: uuid.UUID,
    payload: PublicEnquirySubmitRequest,
    db: Session = Depends(get_db),
    ip: str = Depends(client_ip),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> PublicEnquirySubmitResponse:
    result = PublicEnquiryService(db).submit(
        public_key,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        email=payload.email,
        company=payload.company,
        service_id=payload.service_id,
        preferred_contact_method=payload.preferred_contact_method,
        consent_given=payload.consent_given,
        answers=[AnswerInput(question_id=a.question_id, value=a.value) for a in payload.answers],
        honeypot_value=payload.website,
        utm={
            "utm_source": payload.utm_source,
            "utm_medium": payload.utm_medium,
            "utm_campaign": payload.utm_campaign,
            "utm_term": payload.utm_term,
            "utm_content": payload.utm_content,
        },
        referrer_url=payload.referrer_url,
        ip_address=ip,
        idempotency_key=idempotency_key,
    )
    db.commit()
    if not result.accepted:
        return PublicEnquirySubmitResponse(reference_number=None, message="Thank you.")
    return PublicEnquirySubmitResponse(
        reference_number=result.reference_number,
        message="Thank you. Your enquiry has been received.",
    )
