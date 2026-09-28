"""Candidate knowledge base: the only source the answer engine may use.

Facts are usable for answers only when VERIFIED (or INFERRED when the
candidate explicitly allows inferred answers). EXTRACTED facts (straight
from CV parsing) must be confirmed first. UNKNOWN never becomes YES.
"""
from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from ..models import CandidateFact, FactStatus

PROFESSIONAL_TYPES = {"full-time", "part-time", "contract", "freelance", "temporary", "self-employed"}
NON_PROFESSIONAL_TYPES = {"internship", "academic", "volunteer", "personal", "apprenticeship"}

SKILL_ALIASES = {
    "js": "javascript", "ts": "typescript", "k8s": "kubernetes", "py": "python", "postgres": "postgresql",
    "ms excel": "excel", "microsoft excel": "excel", "gcp": "google cloud", "aws": "amazon web services",
    "security information and event management": "siem", "ml": "machine learning", "ai": "artificial intelligence",
    "node": "node.js", "nodejs": "node.js", "reactjs": "react", "react.js": "react",
}


def norm(s: str) -> str:
    s = re.sub(r"\s+", " ", s.strip().lower())
    s = re.sub(r"[^\w.+#/ -]", "", s)
    return SKILL_ALIASES.get(s, s)


@dataclass(frozen=True)
class FactRef:
    """A value plus where it came from."""

    value: str | None
    status: str  # VERIFIED | INFERRED | DERIVED | UNKNOWN | CONFLICT | NOT_APPLICABLE
    fact_ids: tuple[int, ...] = ()
    sources: tuple[str, ...] = ()
    note: str | None = None

    @property
    def known(self) -> bool:
        return self.status in {"VERIFIED", "DERIVED", "INFERRED"} and self.value not in (None, "")


UNKNOWN = FactRef(None, "UNKNOWN")


@dataclass
class Entry:
    group_key: str
    fields: dict[str, CandidateFact] = field(default_factory=dict)

    def get(self, k: str) -> str | None:
        f = self.fields.get(k)
        return f.value if f else None


def _month(d: str | None, today: dt.date) -> dt.date | None:
    if not d:
        return None
    if d == "present":
        return today
    m = re.fullmatch(r"(\d{4})-(\d{2})", d)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), 1)
    return None  # year-only dates are too coarse to compute experience safely


class KnowledgeBase:
    def __init__(self, facts: Iterable[CandidateFact], allow_inferred: bool = False, today: dt.date | None = None):
        self.allow_inferred = allow_inferred
        self.today = today or dt.date.today()
        self.all = list(facts)
        usable = {FactStatus.VERIFIED.value} | ({FactStatus.INFERRED.value} if allow_inferred else set())
        self.usable = [f for f in self.all if f.status in usable]
        self._by_key: dict[tuple[str, str], list[CandidateFact]] = defaultdict(list)
        self._groups: dict[str, Entry] = {}
        for f in self.usable:
            if f.group_key:
                self._groups.setdefault(f.group_key, Entry(f.group_key)).fields[f.key] = f
            else:
                self._by_key[(f.category, f.key.lower())].append(f)

    # ------------------------------------------------------------------ scalar facts

    def get(self, category: str, key: str) -> FactRef:
        rows = self._by_key.get((category, key.lower()), [])
        if not rows:
            return UNKNOWN
        values = {(r.value or "").strip().lower() for r in rows}
        if len(values) > 1:
            return FactRef(None, "CONFLICT", tuple(r.id for r in rows), tuple(r.source for r in rows),
                           note=f"Conflicting values for {category}.{key}")
        r = rows[0]
        return FactRef(r.value, "VERIFIED" if r.status == FactStatus.VERIFIED.value else "INFERRED",
                       tuple(x.id for x in rows), tuple(x.source for x in rows))

    def category(self, category: str) -> list[CandidateFact]:
        return [f for f in self.usable if f.category == category and not f.group_key]

    # ------------------------------------------------------------------ grouped entries

    def entries(self, prefix: str) -> list[Entry]:
        return [e for k, e in sorted(self._groups.items()) if k.startswith(prefix)]

    def employment(self) -> list[Entry]:
        return self.entries("emp:")

    def education(self) -> list[Entry]:
        return self.entries("edu:")

    def projects(self) -> list[Entry]:
        return self.entries("proj:")

    # ------------------------------------------------------------------ derived facts

    def professional_years(self) -> FactRef:
        explicit = self.get("experience", "total_professional_years")
        computed = self._computed_professional_years()
        if explicit.status == "CONFLICT":
            return explicit
        if explicit.known and computed.known:
            if abs(float(explicit.value) - float(computed.value)) >= 1.0:
                return FactRef(None, "CONFLICT", explicit.fact_ids + computed.fact_ids,
                               note=f"Stated {explicit.value} years vs {computed.value} computed from employment dates")
            return explicit
        return explicit if explicit.known else computed

    def _computed_professional_years(self) -> FactRef:
        jobs = self.employment()
        if not jobs:
            return UNKNOWN
        intervals: list[tuple[dt.date, dt.date]] = []
        ids: list[int] = []
        for e in jobs:
            etype = (e.get("employment_type") or "").lower()
            if not etype:
                return FactRef(None, "UNKNOWN", note=f"Employment type not verified for {e.group_key}")
            if etype in NON_PROFESSIONAL_TYPES:
                continue
            if etype not in PROFESSIONAL_TYPES:
                return FactRef(None, "UNKNOWN", note=f"Unrecognised employment type '{etype}'")
            s, en = _month(e.get("start_date"), self.today), _month(e.get("end_date"), self.today)
            if not s or not en or en < s:
                return FactRef(None, "UNKNOWN", note=f"Month-precision dates not verified for {e.group_key}")
            intervals.append((s, en))
            ids += [f.id for f in e.fields.values()]
        if not intervals:
            return FactRef("0", "DERIVED", tuple(ids), ("employment_history",),
                           note="No professional (non-internship/academic) employment verified")
        intervals.sort()
        merged = [list(intervals[0])]
        for s, e in intervals[1:]:
            if s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        months = sum((e.year - s.year) * 12 + (e.month - s.month) for s, e in merged)
        years = round(months / 12, 1)
        return FactRef(f"{years:g}", "DERIVED", tuple(ids), ("employment_history",),
                       note="Computed from verified professional employment dates")

    def skill(self, name: str) -> FactRef:
        """Returns the verified context ('professional'|'academic'|'personal'|...) for a skill."""
        n = norm(name)
        rows = [f for f in self.category("skill") if norm(f.key) == n]
        if not rows:
            return UNKNOWN
        ctxs = {(r.value or "unknown").lower() for r in rows}
        ctx = "professional" if "professional" in ctxs else sorted(ctxs)[0]
        st = "VERIFIED" if all(r.status == FactStatus.VERIFIED.value for r in rows) else "INFERRED"
        return FactRef(ctx, st, tuple(r.id for r in rows), tuple(r.source for r in rows))

    def skill_professional_years(self, name: str) -> FactRef:
        n = norm(name)
        rows = [f for f in self.category("skill_years") if norm(f.key) == n]
        if rows:
            r = rows[0]
            return FactRef(r.value, "VERIFIED", (r.id,), (r.source,))
        sk = self.skill(name)
        if sk.known and sk.value in NON_PROFESSIONAL_TYPES | {"academic", "personal"}:
            return FactRef("0", "DERIVED", sk.fact_ids, sk.sources,
                           note=f"{name} experience is verified as {sk.value} only (not professional)")
        return FactRef(None, "UNKNOWN", note=f"No verified professional years for {name}")

    def verified_skill_names(self) -> set[str]:
        return {norm(f.key) for f in self.category("skill")}

    def all_text_values(self) -> str:
        """Concatenated verified values; used by the grounding validator."""
        return "\n".join(f"{f.key}: {f.value or ''}" for f in self.usable)

    def facts_for_prompt(self) -> list[dict]:
        return [
            {"id": f.id, "category": f.category, "group": f.group_key, "key": f.key, "value": f.value, "status": f.status}
            for f in self.usable
        ]
