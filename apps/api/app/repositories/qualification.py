import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.qualification import QualificationForm, QualificationQuestion, QualificationRule


class QualificationFormRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_default_for_tenant(self, tenant_id: uuid.UUID) -> QualificationForm | None:
        stmt = select(QualificationForm).where(
            QualificationForm.tenant_id == tenant_id, QualificationForm.is_default.is_(True)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_id_for_tenant(
        self, tenant_id: uuid.UUID, form_id: uuid.UUID
    ) -> QualificationForm | None:
        stmt = select(QualificationForm).where(
            QualificationForm.tenant_id == tenant_id, QualificationForm.id == form_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(
        self, *, tenant_id: uuid.UUID, name: str, is_default: bool = True
    ) -> QualificationForm:
        form = QualificationForm(tenant_id=tenant_id, name=name, is_default=is_default)
        self.db.add(form)
        self.db.flush()
        return form


class QualificationQuestionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id_for_form(
        self, form_id: uuid.UUID, question_id: uuid.UUID
    ) -> QualificationQuestion | None:
        stmt = select(QualificationQuestion).where(
            QualificationQuestion.form_id == form_id, QualificationQuestion.id == question_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        form_id: uuid.UUID,
        field_definition_id: uuid.UUID,
        sort_order: int,
        is_required: bool,
        help_text: str | None = None,
    ) -> QualificationQuestion:
        question = QualificationQuestion(
            form_id=form_id,
            field_definition_id=field_definition_id,
            sort_order=sort_order,
            is_required=is_required,
            help_text=help_text,
        )
        self.db.add(question)
        self.db.flush()
        return question

    def deactivate(self, question: QualificationQuestion) -> QualificationQuestion:
        question.is_active = False
        self.db.flush()
        return question

    def reorder(self, question: QualificationQuestion, sort_order: int) -> QualificationQuestion:
        question.sort_order = sort_order
        self.db.flush()
        return question


class QualificationRuleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        question_id: uuid.UUID,
        depends_on_question_id: uuid.UUID,
        depends_on_value: str,
        operator: str = "equals",
        action: str = "show",
    ) -> QualificationRule:
        rule = QualificationRule(
            question_id=question_id,
            depends_on_question_id=depends_on_question_id,
            depends_on_value=depends_on_value,
            operator=operator,
            action=action,
        )
        self.db.add(rule)
        self.db.flush()
        return rule

    def delete(self, rule: QualificationRule) -> None:
        self.db.delete(rule)
        self.db.flush()
