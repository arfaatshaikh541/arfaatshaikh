import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.custom_field import CustomFieldDefinition, CustomFieldOption


class CustomFieldRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_tenant(
        self, tenant_id: uuid.UUID, *, entity_type: str = "lead", active_only: bool = False
    ) -> list[CustomFieldDefinition]:
        stmt = select(CustomFieldDefinition).where(
            CustomFieldDefinition.tenant_id == tenant_id,
            CustomFieldDefinition.entity_type == entity_type,
        )
        if active_only:
            stmt = stmt.where(CustomFieldDefinition.is_active.is_(True))
        stmt = stmt.order_by(CustomFieldDefinition.sort_order)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id_for_tenant(
        self, tenant_id: uuid.UUID, field_id: uuid.UUID
    ) -> CustomFieldDefinition | None:
        stmt = select(CustomFieldDefinition).where(
            CustomFieldDefinition.tenant_id == tenant_id, CustomFieldDefinition.id == field_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_key_for_tenant(
        self, tenant_id: uuid.UUID, field_key: str, *, entity_type: str = "lead"
    ) -> CustomFieldDefinition | None:
        stmt = select(CustomFieldDefinition).where(
            CustomFieldDefinition.tenant_id == tenant_id,
            CustomFieldDefinition.entity_type == entity_type,
            CustomFieldDefinition.field_key == field_key,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        tenant_id: uuid.UUID,
        field_key: str,
        label: str,
        field_type: str,
        is_required: bool,
        sort_order: int,
        options: list[tuple[str, str]] | None = None,
        entity_type: str = "lead",
    ) -> CustomFieldDefinition:
        field = CustomFieldDefinition(
            tenant_id=tenant_id,
            entity_type=entity_type,
            field_key=field_key,
            label=label,
            field_type=field_type,
            is_required=is_required,
            sort_order=sort_order,
        )
        self.db.add(field)
        self.db.flush()
        for index, (value, option_label) in enumerate(options or []):
            self.db.add(
                CustomFieldOption(
                    field_definition_id=field.id, value=value, label=option_label, sort_order=index
                )
            )
        self.db.flush()
        return field

    def deactivate(self, field: CustomFieldDefinition) -> CustomFieldDefinition:
        field.is_active = False
        self.db.flush()
        return field
