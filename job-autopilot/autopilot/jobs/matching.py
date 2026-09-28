"""Transparent requirement matching and the rule-based apply decision.

The score is the share of *evaluable* weighted criteria that match. It says how
well the posting's stated requirements line up with the verified profile. It
is NOT a prediction of being hired.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from ..models import Job
from ..profile.knowledge import KnowledgeBase, norm
from ..profile.schema import Preferences, Rules
from ..questions.engine import find_country

SUPPORTED_APPLY_METHODS = {"greenhouse_hosted_form", "lever_hosted_form", "ashby_hosted_form"}

MATCH, PARTIAL, NO_MATCH, UNKNOWN, NOT_VERIFIED, NOT_CONFIGURED, DISQUALIFIED = (
    "MATCH", "PARTIAL", "DOES NOT MATCH", "UNKNOWN", "NOT VERIFIED", "NOT CONFIGURED", "DISQUALIFIED",
)
_SCORE = {MATCH: 1.0, PARTIAL: 0.5, NO_MATCH: 0.0, NOT_VERIFIED: 0.0, DISQUALIFIED: 0.0}


@dataclass
class Criterion:
    name: str
    status: str
    detail: str
    weight: float = 1.0


def _contains_phrase(hay: str, needle: str) -> bool:
    toks = [t for t in re.split(r"\W+", needle.lower()) if t]
    h = set(re.split(r"\W+", hay.lower()))
    return bool(toks) and all(t in h for t in toks)


def _salary_monthly(amount: float, interval: str | None) -> float | None:
    i = (interval or "").lower()
    if "year" in i or "annual" in i:
        return amount / 12
    if "month" in i:
        return amount
    if "hour" in i:
        return amount * 173
    return None


def evaluate(job: Job, prefs: Preferences, kb: KnowledgeBase) -> list[Criterion]:
    c: list[Criterion] = []
    title = job.title or ""
    desc = job.description_text or ""
    text = f"{title}\n{desc}"

    # Disqualifiers
    for comp in prefs.exclude_companies:
        if job.company and norm(comp) == norm(job.company):
            c.append(Criterion("Excluded company", DISQUALIFIED, job.company, 0))
    for kw in prefs.exclude_keywords:
        if _contains_phrase(title, kw):
            c.append(Criterion("Excluded keyword", DISQUALIFIED, f"'{kw}' in title", 0))

    # Role
    if prefs.target_roles:
        hit = next((r for r in prefs.target_roles if _contains_phrase(title, r)), None)
        c.append(Criterion("Target role", MATCH if hit else NO_MATCH, f"{title} ~ {hit}" if hit else title, 3))
    else:
        c.append(Criterion("Target role", NOT_CONFIGURED, "No target roles configured", 0))

    # Location / workplace
    if prefs.target_locations or prefs.workplace_types:
        loc = job.location
        ok_remote = job.workplace_type == "remote" and "remote" in prefs.workplace_types
        loc_hit = loc and any(_contains_phrase(loc, l) or (find_country(l) and find_country(l) == find_country(loc))
                              for l in prefs.target_locations)
        if ok_remote or loc_hit:
            c.append(Criterion("Location", MATCH, f"{loc or 'UNKNOWN'} ({job.workplace_type or 'workplace UNKNOWN'})", 2))
        elif not loc and not job.workplace_type:
            c.append(Criterion("Location", UNKNOWN, "Location not stated", 2))
        else:
            c.append(Criterion("Location", NO_MATCH, f"{loc or 'UNKNOWN'} ({job.workplace_type or 'workplace UNKNOWN'})", 2))
        if prefs.workplace_types:
            if job.workplace_type is None:
                c.append(Criterion("Workplace type", UNKNOWN, "Not stated in posting", 1))
            else:
                st = MATCH if job.workplace_type in prefs.workplace_types else NO_MATCH
                c.append(Criterion("Workplace type", st, job.workplace_type, 1))
    else:
        c.append(Criterion("Location", NOT_CONFIGURED, "No target locations configured", 0))

    if prefs.max_commute_km is not None:
        c.append(Criterion("Commute", UNKNOWN, "Commute distance cannot be determined from postings", 0))

    # Employment type
    if prefs.employment_types:
        if not job.employment_type:
            c.append(Criterion("Employment type", UNKNOWN, "Not stated", 1))
        else:
            et = norm(job.employment_type).replace(" ", "-")
            st = MATCH if any(norm(x).replace(" ", "-") in et for x in prefs.employment_types) else NO_MATCH
            c.append(Criterion("Employment type", st, job.employment_type, 1))

    # Salary
    if prefs.min_salary.amount:
        if job.salary_max is None and job.salary_min is None:
            c.append(Criterion("Salary", UNKNOWN, "Salary not stated (UNKNOWN)", 1))
        elif prefs.min_salary.currency and job.salary_currency and prefs.min_salary.currency.upper() != job.salary_currency.upper():
            c.append(Criterion("Salary", UNKNOWN, f"Posting currency {job.salary_currency} differs; no FX conversion", 1))
        else:
            top = job.salary_max or job.salary_min
            jm = _salary_monthly(top, job.salary_interval)
            pm = _salary_monthly(prefs.min_salary.amount, prefs.min_salary.interval)
            if jm is None or pm is None:
                c.append(Criterion("Salary", UNKNOWN, f"Pay interval not stated ({job.salary_text or top})", 1))
            else:
                c.append(Criterion("Salary", MATCH if jm >= pm else NO_MATCH,
                                   f"up to {top:,.0f} {job.salary_currency or ''} {job.salary_interval or ''}", 1))

    # Experience
    if job.experience_years_min is not None:
        py = kb.professional_years()
        req = job.experience_years_min
        if prefs.max_required_experience_years is not None and req > prefs.max_required_experience_years:
            c.append(Criterion("Experience requirement", NO_MATCH,
                               f"{req:g}+ years required > your limit {prefs.max_required_experience_years:g}", 2))
        elif py.known:
            have = float(py.value)
            c.append(Criterion("Experience", MATCH if have >= req else NO_MATCH,
                               f"{req:g}+ years required; verified professional: {have:g}", 2))
        else:
            c.append(Criterion("Experience", UNKNOWN, f"{req:g}+ years required; your professional years: {py.status}", 2))

    # Skills
    for sk in job.skills or []:
        ref = kb.skill(sk)
        if not ref.known:
            c.append(Criterion(f"Skill: {sk}", NOT_VERIFIED, "Not in verified skills", 1))
        elif ref.value == "professional":
            c.append(Criterion(f"Skill: {sk}", MATCH, "Verified (professional)", 1))
        else:
            c.append(Criterion(f"Skill: {sk}", PARTIAL, f"Verified ({ref.value})", 1))
    if prefs.required_skills:
        hit = [s for s in prefs.required_skills if _contains_phrase(text, s)]
        c.append(Criterion("Your required skills in posting", MATCH if hit else NO_MATCH,
                           ", ".join(hit) or "none mentioned", 2))
    for s in prefs.optional_skills:
        if _contains_phrase(text, s):
            c.append(Criterion(f"Optional skill: {s}", MATCH, "Mentioned in posting", 0.5))
    if prefs.keywords:
        hit = [k for k in prefs.keywords if _contains_phrase(text, k)]
        c.append(Criterion("Keywords", MATCH if hit else NO_MATCH, ", ".join(hit) or "none", 1))

    # Education
    if re.search(r"\b(bachelor|degree|b\.?sc|bsc|master)\b", desc, re.I):
        degs = [e.get("degree") for e in kb.education() if e.get("degree")]
        c.append(Criterion("Education", MATCH if degs else NOT_VERIFIED,
                           f"Posting mentions a degree; verified: {', '.join(degs) or 'none'}", 1))

    # Work authorisation
    country = find_country(job.location)
    if country and job.workplace_type != "remote":
        auth = kb.get("work_authorization", f"authorized:{country}")
        if auth.known:
            yes = auth.value.strip().lower() in {"yes", "true"}
            c.append(Criterion("Work authorization", MATCH if yes else NO_MATCH, f"{country}: {auth.value}", 2))
        else:
            c.append(Criterion("Work authorization", UNKNOWN, f"{country}: not verified", 2))
    return c


def score(criteria: list[Criterion]) -> float:
    ev = [x for x in criteria if x.status in _SCORE and x.weight > 0]
    tw = sum(x.weight for x in ev)
    return round(100 * sum(_SCORE[x.status] * x.weight for x in ev) / tw, 1) if tw else 0.0


@dataclass
class Decision:
    decision: str  # APPLY | SKIP | REVIEW
    reasons: list[str]


def decide(job: Job, criteria: list[Criterion], sc: float, prefs: Preferences, rules: Rules,
           platform_automatable: bool) -> Decision:
    reasons: list[str] = []
    by = {x.name: x for x in criteria}
    if any(x.status == DISQUALIFIED for x in criteria):
        return Decision("SKIP", [f"Disqualified: {x.name} ({x.detail})" for x in criteria if x.status == DISQUALIFIED])
    if job.duplicate_of_id is not None:
        return Decision("SKIP", [f"Duplicate of job #{job.duplicate_of_id}"])
    if not platform_automatable or job.apply_method not in SUPPORTED_APPLY_METHODS:
        return Decision("SKIP", [f"Application method {job.apply_method} cannot be completed automatically"])
    fails = []
    if rules.require_target_role and by.get("Target role", Criterion("", NOT_CONFIGURED, "")).status != MATCH:
        fails.append("Not a target role" if "Target role" in by and by["Target role"].status != NOT_CONFIGURED
                     else "Target roles NOT CONFIGURED")
    if rules.require_location_match:
        loc = by.get("Location")
        if loc is None or loc.status != MATCH:
            fails.append(f"Location not acceptable ({loc.status if loc else 'NOT CONFIGURED'})")
    if rules.require_employment_type_match and "Employment type" in by and by["Employment type"].status == NO_MATCH:
        fails.append("Employment type not acceptable")
    if rules.skip_if_experience_exceeds:
        for n in ("Experience", "Experience requirement"):
            if n in by and by[n].status == NO_MATCH:
                fails.append(f"Experience: {by[n].detail}")
    if "Work authorization" in by and by["Work authorization"].status == NO_MATCH:
        fails.append(f"Work authorization: {by['Work authorization'].detail}")
    if rules.require_min_score and sc < prefs.min_match_score:
        fails.append(f"Score {sc} < threshold {prefs.min_match_score}")
    if fails:
        return Decision(rules.on_rule_failure, fails)
    reasons.append(f"All auto-apply rules satisfied (score {sc})")
    return Decision("APPLY", reasons)


def criteria_json(criteria: list[Criterion]) -> list[dict]:
    return [asdict(x) for x in criteria]
