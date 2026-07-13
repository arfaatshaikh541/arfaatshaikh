from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.custom_field import FIELD_TYPES, SELECT_FIELD_TYPES
from app.models.qualification import QualificationForm, QualificationQuestion, QualificationRule
from app.repositories.custom_field import CustomFieldRepository
from app.repositories.qualification import (
    QualificationFormRepository,
    QualificationQuestionRepository,
    QualificationRuleRepository,
)
from app.services.catalog_service import slugify
from app.services.errors import NotFoundError, ValidationError


class QualificationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.forms = QualificationFormRepository(db)
        self.questions = QualificationQuestionRepository(db)
        self.rules = QualificationRuleRepository(db)
        self.fields = CustomFieldRepository(db)

    def get_or_create_default_form(self, tenant_id: uuid.UUID) -> QualificationForm:
        form = self.forms.get_default_for_tenant(tenant_id)
        if form is None:
            form = self.forms.create(
                tenant_id=tenant_id, name="Default Enquiry Form", is_default=True
            )
        return form

    def add_question(
        self,
        tenant_id: uuid.UUID,
        *,
        label: str,
        field_type: str,
        is_required: bool,
        help_text: str | None = None,
        options: list[str] | None = None,
    ) -> QualificationQuestion:
        if field_type not in FIELD_TYPES:
            raise ValidationError(f"Unknown field type '{field_type}'.")
        if field_type in SELECT_FIELD_TYPES and not options:
            raise ValidationError("Select questions require at least one option.")

        form = self.get_or_create_default_form(tenant_id)
        field_key = self._unique_field_key(tenant_id, label)
        field_options = [(slugify(o), o) for o in (options or [])]
        field_definition = self.fields.create(
            tenant_id=tenant_id,
            field_key=field_key,
            label=label,
            field_type=field_type,
            is_required=is_required,
            sort_order=len(form.questions),
            options=field_options,
        )
        return self.questions.create(
            form_id=form.id,
            field_definition_id=field_definition.id,
            sort_order=len(form.questions),
            is_required=is_required,
            help_text=help_text,
        )

    def _unique_field_key(self, tenant_id: uuid.UUID, label: str) -> str:
        base = slugify(label) or "question"
        candidate = base
        suffix = 1
        while self.fields.get_by_key_for_tenant(tenant_id, candidate) is not None:
            suffix += 1
            candidate = f"{base}-{suffix}"
        return candidate

    def deactivate_question(
        self, tenant_id: uuid.UUID, question_id: uuid.UUID
    ) -> QualificationQuestion:
        form = self.get_or_create_default_form(tenant_id)
        question = self.questions.get_by_id_for_form(form.id, question_id)
        if question is None:
            raise NotFoundError("Question not found.")
        return self.questions.deactivate(question)

    def reorder_questions(
        self, tenant_id: uuid.UUID, ordered_question_ids: list[uuid.UUID]
    ) -> list[QualificationQuestion]:
        form = self.get_or_create_default_form(tenant_id)
        by_id = {q.id: q for q in form.questions}
        if not set(ordered_question_ids).issubset(by_id.keys()):
            raise ValidationError("Unknown question id in reorder list.")
        for index, question_id in enumerate(ordered_question_ids):
            self.questions.reorder(by_id[question_id], index)
        return self.get_or_create_default_form(tenant_id).questions

    def add_rule(
        self,
        tenant_id: uuid.UUID,
        *,
        question_id: uuid.UUID,
        depends_on_question_id: uuid.UUID,
        depends_on_value: str,
    ) -> QualificationRule:
        form = self.get_or_create_default_form(tenant_id)
        question = self.questions.get_by_id_for_form(form.id, question_id)
        depends_on = self.questions.get_by_id_for_form(form.id, depends_on_question_id)
        if question is None or depends_on is None:
            raise ValidationError("Both questions must belong to this tenant's qualification form.")
        return self.rules.create(
            question_id=question_id,
            depends_on_question_id=depends_on_question_id,
            depends_on_value=depends_on_value,
        )
