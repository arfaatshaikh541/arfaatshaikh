"""User-editable runtime settings persisted in the ``settings`` table.

Defaults are conservative configuration defaults (mode = DRY_RUN, automation
= STOPPED). They contain no candidate data.
"""
from __future__ import annotations

from typing import Literal, TypeVar

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from .models import Setting, utcnow


class AutomationSettings(BaseModel):
    state: Literal["STOPPED", "RUNNING", "PAUSED"] = "STOPPED"
    mode: Literal["DRY_RUN", "LIVE"] = "DRY_RUN"
    search_interval_minutes: int = Field(30, ge=5, le=1440)
    min_minutes_between_applications: int = Field(10, ge=1, le=1440)
    max_applications_per_day: int = Field(15, ge=0, le=200)
    max_applications_per_platform_per_day: int = Field(10, ge=0, le=200)
    allowed_hours_start: int = Field(8, ge=0, le=23)
    allowed_hours_end: int = Field(20, ge=1, le=24)
    timezone: str = "Asia/Dubai"
    daily_report_time: str = "20:00"
    max_retries: int = Field(3, ge=0, le=10)
    retry_base_seconds: int = Field(60, ge=5, le=3600)
    apply_to_duplicates: bool = False
    # Minimum seconds between HTTP requests to the same host.
    request_min_interval_seconds: float = Field(3.0, ge=1.0, le=600)
    # Human verification gateway
    hold_for_verification: bool = True
    verification_timeout_minutes: int = Field(15, ge=1, le=240)
    # Hard cap on how long any held browser session may stay alive.
    browser_session_timeout_minutes: int = Field(30, ge=2, le=480)
    max_open_verification_sessions: int = Field(2, ge=0, le=10)
    notification_retry_minutes: int = Field(5, ge=1, le=240)
    max_notification_attempts: int = Field(6, ge=1, le=50)
    # Whole-application wall-clock limit (excluding time spent waiting for a human).
    application_timeout_minutes: int = Field(20, ge=2, le=240)

    @field_validator("daily_report_time")
    @classmethod
    def _hhmm(cls, v: str) -> str:
        h, m = v.split(":")
        if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
            raise ValueError("daily_report_time must be HH:MM")
        return f"{int(h):02d}:{int(m):02d}"

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        from zoneinfo import ZoneInfo

        ZoneInfo(v)
        return v


class AISettings(BaseModel):
    provider: Literal["none", "anthropic", "openai", "ollama"] = "none"
    model: str = ""
    base_url: str = ""
    # Candidate data is sent to the provider ONLY if this is explicitly true.
    allow_candidate_data: bool = False
    last_check_ok: bool | None = None
    last_check_message: str | None = None
    last_check_at: str | None = None


class NotificationSettings(BaseModel):
    """Channels are used only when enabled here AND their secret is stored in the vault
    (notify:smtp password, notify:telegram bot token). Dashboard notifications always work."""

    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = Field(587, ge=1, le=65535)
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    smtp_username: str = ""
    email_from: str = ""
    email_to: str = ""
    telegram_enabled: bool = False
    telegram_chat_id: str = ""
    telegram_api_base: str = "https://api.telegram.org"


class ReconcileSettings(BaseModel):
    """Read-only IMAP access used to find employer confirmation emails for UNKNOWN applications.
    The IMAP password (app password) is stored in the vault as reconcile:imap."""

    imap_enabled: bool = False
    imap_host: str = ""
    imap_port: int = Field(993, ge=1, le=65535)
    imap_username: str = ""
    imap_folder: str = "INBOX"
    lookback_days: int = Field(3, ge=1, le=30)


_KEYS = {AutomationSettings: "automation", AISettings: "ai", NotificationSettings: "notifications",
         ReconcileSettings: "reconcile"}
T = TypeVar("T", AutomationSettings, AISettings, NotificationSettings, ReconcileSettings)


def load(s: Session, cls: type[T]) -> T:
    row = s.get(Setting, _KEYS[cls])
    return cls.model_validate(row.value) if row else cls()


def save(s: Session, obj: BaseModel) -> None:
    key = _KEYS[type(obj)]
    row = s.get(Setting, key, with_for_update=True)
    if row is None:
        s.add(Setting(key=key, value=obj.model_dump(), updated_at=utcnow()))
    else:
        row.value = obj.model_dump()
        row.updated_at = utcnow()
    s.flush()
