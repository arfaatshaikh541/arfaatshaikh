"""Exact-text verification against the published Qur'an and Hadith text.

Reports only whether a normalised Arabic passage occurs verbatim inside published text and where.
It never guesses, paraphrases, or grades authenticity.
"""
from __future__ import annotations

import re
import time
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_SUBSTITUTIONS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})
_cache: dict[str, tuple[float, list[tuple[str, str, str]]]] = {}
CACHE_SECONDS = 60.0  # short on purpose: publication changes must take effect quickly


def clear_cache() -> None:
    """Forget the cached corpus (called whenever a dataset is published, hidden or re-synced)."""
    _cache.clear()


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.category(c).startswith("M") and c != "ـ").translate(_SUBSTITUTIONS)
    return " ".join(re.sub(r"[^ء-ي ]", " ", text).split())


async def _corpus(db: AsyncSession) -> list[tuple[str, str, str]]:
    from app.models.hadith import HadithCollection, HadithNarration
    from app.models.quran import QuranAyah

    cached = _cache.get("all")
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]
    rows: list[tuple[str, str, str]] = []
    for ref, text in (await db.execute(select(QuranAyah.canonical_reference, QuranAyah.arabic_text).where(QuranAyah.published.is_(True)))).all():
        rows.append(("quran", f"Qur'an {ref}", normalise(text)))
    query = (select(HadithCollection.display_title, HadithNarration.canonical_reference, HadithNarration.arabic_matn)
             .join(HadithCollection, HadithCollection.id == HadithNarration.collection_id)
             .where(HadithNarration.published.is_(True), HadithCollection.published.is_(True)))
    for title, ref, text in (await db.execute(query)).all():
        rows.append(("hadith", f"{title}, {ref}", normalise(text)))
    _cache["all"] = (time.monotonic(), rows)
    return rows


async def verify_text(db: AsyncSession, text: str, limit: int = 25) -> dict:
    needle = normalise(text)
    words = needle.split()
    if len(words) < 3:
        return {"status": "too_short", "query_words": len(words), "matches": []}
    matches = []
    for kind, ref, hay in await _corpus(db):
        pos = f" {hay} ".find(f" {needle} ")
        if pos >= 0:
            matches.append({"corpus": kind, "reference": ref})
            if len(matches) >= limit:
                break
    return {"status": "found" if matches else "not_found", "query_words": len(words), "matches": matches,
            "note": "Checks for an exact occurrence in the published text only. It does not assess authenticity or grading."}
