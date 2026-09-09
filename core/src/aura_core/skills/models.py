"""Persisted Skill schema: a named, reusable, ordered composition of
existing Capabilities. A Skill never contains arbitrary new code -- each
step names a capability_name that must already exist in the
CapabilityRegistry (enforced by skills/builder.py, not here), and every
step still executes through the real Action Broker exactly like any
other submission. This is what lets AURA "learn" a new workflow (per the
product brief's "preserve it for future use") without ever generating
and running unreviewed code.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..memory.models import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SkillStep:
    capability_name: str
    params_template: dict = field(default_factory=dict)
    on_failure: str = "abort"  # "abort" | "continue"

    def to_dict(self) -> dict:
        return {"capability_name": self.capability_name, "params_template": self.params_template, "on_failure": self.on_failure}

    @staticmethod
    def from_dict(data: dict) -> "SkillStep":
        return SkillStep(
            capability_name=data["capability_name"],
            params_template=data.get("params_template", {}),
            on_failure=data.get("on_failure", "abort"),
        )


class SkillRecord(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    domain: Mapped[str] = mapped_column(String(100), default="general")
    steps_json: Mapped[str] = mapped_column(Text, default="[]")
    created_by: Mapped[str] = mapped_column(String(50), default="owner")  # "builtin" | "owner" | "auto"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def steps(self) -> list[SkillStep]:
        return [SkillStep.from_dict(d) for d in json.loads(self.steps_json)]
