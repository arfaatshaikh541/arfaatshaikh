"""Normalisation, deduplication, ingestion of discovered jobs."""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..connectors.base import NormalizedJob
from ..models import Job, utcnow
from ..questions.grounding import SKILL_VOCAB

_EXP_RE = re.compile(
    r"(?P<min>\d{1,2})\s*(?:\+|plus)?\s*(?:(?:-|–|to)\s*(?P<max>\d{1,2})\s*)?(?:years?|yrs?)(?:['’]s?)?\s+"
    r"(?:of\s+)?(?:[\w/&-]+\s+){0,4}?experience",
    re.I,
)
_SALARY_RE = re.compile(
    r"(?P<cur>AED|USD|EUR|GBP|SAR|QAR|INR|\$|£|€)\s?(?P<a>\d[\d,]*(?:\.\d+)?)\s*(?P<k>k)?\s*(?:-|–|to)\s*"
    r"(?:AED|USD|EUR|GBP|SAR|QAR|INR|\$|£|€)?\s?(?P<b>\d[\d,]*(?:\.\d+)?)\s*(?P<k2>k)?",
    re.I,
)
_SYM = {"$": "USD", "£": "GBP", "€": "EUR"}


def extract_experience(text: str | None) -> tuple[float | None, str | None]:
    if not text:
        return None, None
    mins = []
    snippet = None
    for m in _EXP_RE.finditer(text):
        v = float(m.group("min"))
        if v <= 30:
            mins.append(v)
            snippet = snippet or text[max(0, m.start() - 60): m.end() + 20].strip()
    return (min(mins) if mins else None), snippet


def extract_salary(text: str | None) -> tuple[float | None, float | None, str | None, str | None]:
    """Only an explicit currency range in the posting counts; otherwise UNKNOWN."""
    if not text:
        return None, None, None, None
    m = _SALARY_RE.search(text)
    if not m:
        return None, None, None, None
    a = float(m.group("a").replace(",", "")) * (1000 if m.group("k") else 1)
    b = float(m.group("b").replace(",", "")) * (1000 if m.group("k2") or m.group("k") else 1)
    cur = _SYM.get(m.group("cur"), m.group("cur").upper())
    return a, b, cur, m.group(0)


def extract_skills(text: str | None, extra_terms: list[str]) -> list[str]:
    if not text:
        return []
    low = text.lower()
    found = []
    for term in sorted(set(SKILL_VOCAB) | {t.lower() for t in extra_terms if t}):
        if re.search(rf"(?<![\w]){re.escape(term)}(?![\w])", low):
            found.append(term)
    return found


def canonical_url(url: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), "", ""))


def _norm_text(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def fingerprint(company: str | None, title: str, location: str | None) -> str:
    """Cross-platform identity of a job: company + title + location."""
    base = "|".join([_norm_text(company), _norm_text(title), _norm_text(location)])
    return hashlib.sha256(base.encode()).hexdigest()


def description_hash(text: str | None) -> str | None:
    if not text:
        return None
    return hashlib.sha256(_norm_text(text)[:5000].encode()).hexdigest()


def find_duplicate(s: Session, job: Job) -> Job | None:
    """An earlier job with the same fingerprint or the same description on another listing."""
    q = select(Job).where(Job.id != job.id, Job.duplicate_of_id.is_(None))
    cand = s.scalar(q.where(Job.fingerprint == job.fingerprint).order_by(Job.id).limit(1))
    if cand is None and job.description_hash and job.company:
        # Same company + same description text + same title (location strings often differ across sites).
        for other in s.scalars(
            q.where(Job.description_hash == job.description_hash, Job.company == job.company).order_by(Job.id)
        ):
            if _norm_text(other.title) == _norm_text(job.title):
                cand = other
                break
    if cand is None:
        cand = s.scalar(q.where(Job.canonical_url == job.canonical_url).order_by(Job.id).limit(1))
    return cand


class InvalidJobData(ValueError):
    pass


def _check_url(u: str | None) -> None:
    if u is not None and urlsplit(u).scheme not in ("http", "https"):
        raise InvalidJobData(f"Refusing non-http(s) URL from job source: {u[:80]!r}")


def ingest(s: Session, source_id: int | None, nj: NormalizedJob, skill_terms: list[str]) -> tuple[Job, bool]:
    """Insert or refresh a job. Returns (job, created)."""
    _check_url(nj.url)
    _check_url(nj.apply_url)
    job = s.scalar(
        select(Job).where(Job.platform == nj.platform, Job.board == nj.board, Job.external_id == nj.external_id)
    )
    created = job is None
    if created:
        job = Job(platform=nj.platform, board=nj.board, external_id=nj.external_id, source_id=source_id)
        s.add(job)
    exp_min, exp_text = extract_experience(nj.description_text)
    smin, smax, scur, stext = nj.salary_min, nj.salary_max, nj.salary_currency, nj.salary_text
    if smin is None and smax is None:
        a, b, c, t = extract_salary(nj.description_text)
        if a is not None:
            smin, smax, scur, stext = a, b, c, t
    job.url = nj.url
    job.canonical_url = canonical_url(nj.url)
    job.apply_url = nj.apply_url
    job.apply_method = nj.apply_method
    job.company = nj.company
    job.title = nj.title
    job.location = nj.location
    job.workplace_type = nj.workplace_type
    job.employment_type = nj.employment_type
    job.salary_min, job.salary_max, job.salary_currency = smin, smax, scur
    job.salary_interval = nj.salary_interval
    job.salary_text = stext
    job.experience_years_min, job.experience_text = exp_min, exp_text
    job.skills = extract_skills(nj.description_text, skill_terms)
    job.description_text = nj.description_text
    job.description_hash = description_hash(nj.description_text)
    job.fingerprint = fingerprint(nj.company, nj.title, nj.location)
    job.published_at = nj.published_at
    job.raw = nj.raw
    job.last_seen_at = utcnow()
    s.flush()
    if created:
        dup = find_duplicate(s, job)
        if dup is not None:
            job.duplicate_of_id = dup.id
            job.status = "DUPLICATE"
    return job, created
