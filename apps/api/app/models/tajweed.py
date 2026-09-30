from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class QuranTajweedRule(TimestampMixin, Base):
    __tablename__ = "quran_tajweed_rules"

    rule_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    topic_id: Mapped[str] = mapped_column(String(80), nullable=False)
    topic_label_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    hukum_id: Mapped[str] = mapped_column(String(120), nullable=False)
    label_ar: Mapped[str] = mapped_column(Text, nullable=False)


class QuranAyahTajweed(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quran_ayah_tajweed"

    ayah_id: Mapped[UUID] = mapped_column(ForeignKey("quran_ayahs.id", ondelete="CASCADE"), nullable=False, unique=True)
    marked_text: Mapped[str] = mapped_column(Text, nullable=False)
    spans_json: Mapped[str] = mapped_column(Text, nullable=False)
    corpus_version: Mapped[str] = mapped_column(String(32), nullable=False)
