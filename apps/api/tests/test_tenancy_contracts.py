import pytest
from pydantic import ValidationError
from app.schemas.organisations import OrganisationCreate
from app.db.base import Base
from app import models  # noqa: F401


def test_organisation_slug_contract() -> None:
    value = OrganisationCreate(name="World of Islam Research", slug="world-of-islam-research")
    assert value.slug == "world-of-islam-research"


def test_organisation_slug_rejects_unsafe_characters() -> None:
    with pytest.raises(ValidationError):
        OrganisationCreate(name="Research", slug="../../research")


def test_membership_role_foreign_key_is_tenant_aware() -> None:
    table = Base.metadata.tables["memberships"]
    composite = [fk for fk in table.foreign_key_constraints if len(fk.column_keys) == 2]
    assert any(set(fk.column_keys) == {"role_id", "organisation_id"} for fk in composite)
