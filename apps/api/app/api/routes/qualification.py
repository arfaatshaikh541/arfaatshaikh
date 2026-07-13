from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import MembershipContext, get_current_membership, require_permission
from app.db.session import get_db
from app.schemas.common import MessageResponse
from app.schemas.qualification import (
    QualificationFormOut,
    QualificationQuestionCreate,
    QualificationQuestionOut,
    QualificationRuleCreate,
    QualificationRuleOut,
    QuestionReorderRequest,
)
from app.services.qualification_service import QualificationService

router = APIRouter(prefix="/tenants/me/qualification-form", tags=["qualification"])


@router.get("", response_model=QualificationFormOut)
def get_qualification_form(
    db: Session = Depends(get_db), ctx: MembershipContext = Depends(get_current_membership)
) -> QualificationFormOut:
    form = QualificationService(db).get_or_create_default_form(ctx.tenant_id)
    db.commit()
    return QualificationFormOut.model_validate(form)


@router.post("/questions", response_model=QualificationQuestionOut, status_code=201)
def add_question(
    payload: QualificationQuestionCreate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("settings.manage")),
) -> QualificationQuestionOut:
    question = QualificationService(db).add_question(
        ctx.tenant_id,
        label=payload.label,
        field_type=payload.field_type,
        is_required=payload.is_required,
        help_text=payload.help_text,
        options=payload.options,
    )
    db.commit()
    return QualificationQuestionOut.model_validate(question)


@router.delete("/questions/{question_id}", response_model=MessageResponse)
def deactivate_question(
    question_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("settings.manage")),
) -> MessageResponse:
    QualificationService(db).deactivate_question(ctx.tenant_id, question_id)
    db.commit()
    return MessageResponse(message="Question deactivated.")


@router.post("/questions/reorder", response_model=list[QualificationQuestionOut])
def reorder_questions(
    payload: QuestionReorderRequest,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("settings.manage")),
) -> list[QualificationQuestionOut]:
    questions = QualificationService(db).reorder_questions(ctx.tenant_id, payload.question_ids)
    db.commit()
    return [QualificationQuestionOut.model_validate(q) for q in questions]


@router.post("/rules", response_model=QualificationRuleOut, status_code=201)
def add_rule(
    payload: QualificationRuleCreate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("settings.manage")),
) -> QualificationRuleOut:
    rule = QualificationService(db).add_rule(
        ctx.tenant_id,
        question_id=payload.question_id,
        depends_on_question_id=payload.depends_on_question_id,
        depends_on_value=payload.depends_on_value,
    )
    db.commit()
    return QualificationRuleOut.model_validate(rule)
