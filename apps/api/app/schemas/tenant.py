import re
import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORMModel

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class TenantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=80)
    legal_name: str | None = None
    timezone: str = "Asia/Dubai"
    currency: str = Field(default="AED", min_length=3, max_length=3)
    owner_email: EmailStr
    owner_first_name: str = Field(min_length=1, max_length=100)
    owner_last_name: str = Field(min_length=1, max_length=100)
    owner_password: str = Field(min_length=10, max_length=200)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        if not _SLUG_RE.match(value):
            raise ValueError("slug must be lowercase alphanumeric with single hyphens")
        return value

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return value.upper()


class TenantOut(ORMModel):
    id: uuid.UUID
    slug: str
    public_key: uuid.UUID
    name: str
    legal_name: str | None
    status: str
    timezone: str
    currency: str


class TenantSettingsOut(ORMModel):
    logo_url: str | None
    brand_primary_color: str
    brand_secondary_color: str
    contact_email: str | None
    contact_phone: str | None
    business_hours: dict
    locale: str
    data_retention_days: int
    privacy_text: str | None


class TenantSettingsUpdate(BaseModel):
    logo_url: str | None = None
    brand_primary_color: str | None = None
    brand_secondary_color: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    business_hours: dict | None = None
    locale: str | None = None
    data_retention_days: int | None = Field(default=None, ge=1, le=3650)
    privacy_text: str | None = None

    @field_validator("brand_primary_color", "brand_secondary_color")
    @classmethod
    def validate_hex_color(cls, value: str | None) -> str | None:
        if value is not None and not _HEX_COLOR_RE.match(value):
            raise ValueError("must be a hex color like #F97316")
        return value


class TenantProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    legal_name: str | None = None
    timezone: str | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
