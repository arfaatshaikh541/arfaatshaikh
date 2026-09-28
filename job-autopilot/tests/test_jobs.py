"""Normalisation, dedup, matching and decisions. Job objects here are in-test inputs, never persisted as real data."""
import datetime as dt

from autopilot.connectors.base import NormalizedJob, html_to_text
from autopilot.connectors.discovery import AshbyConnector, GreenhouseConnector, LeverConnector
from autopilot.jobs.matching import decide, evaluate, score
from autopilot.jobs.pipeline import extract_experience, extract_salary, ingest
from autopilot.models import CandidateFact, Job
from autopilot.profile.knowledge import KnowledgeBase
from autopilot.profile.schema import Preferences, Rules


def _nj(**kw):
    base = dict(platform="greenhouse", board="acme", external_id="1", url="https://job-boards.greenhouse.io/acme/jobs/1",
                apply_url="https://job-boards.greenhouse.io/acme/jobs/1", apply_method="greenhouse_hosted_form",
                title="SOC Analyst", company="Acme", location="Dubai, United Arab Emirates",
                description_text="We need 3+ years of SOC experience with SIEM and Python. Bachelor's degree.")
    base.update(kw)
    return NormalizedJob(**base)


def test_extractors_do_not_invent():
    assert extract_experience("Requires 3+ years of relevant experience")[0] == 3
    assert extract_experience("2-4 years experience in IT")[0] == 2
    assert extract_experience("Great team, fast growth")[0] is None
    assert extract_salary("Salary: AED 10,000 - 15,000 per month")[:3] == (10000, 15000, "AED")
    assert extract_salary("Competitive salary") == (None, None, None, None)
    assert "Hello" in html_to_text("&lt;p&gt;Hello &amp;amp; bye&lt;/p&gt;")


def test_ingest_and_cross_platform_dedup(s):
    j1, c1 = ingest(s, None, _nj(), [])
    j1b, c1b = ingest(s, None, _nj(), [])
    assert c1 and not c1b and j1.id == j1b.id  # same listing refreshes, never duplicates
    j2, c2 = ingest(s, None, _nj(platform="lever", board="acme", external_id="abc",
                                 url="https://jobs.lever.co/acme/abc", apply_method="lever_hosted_form"), [])
    assert c2 and j2.duplicate_of_id == j1.id and j2.status == "DUPLICATE"
    j3, _ = ingest(s, None, _nj(external_id="2", title="Data Engineer", url="https://x/2"), [])
    assert j3.duplicate_of_id is None
    assert j1.salary_min is None  # salary UNKNOWN, not defaulted
    assert "siem" in j1.skills and j1.experience_years_min == 3


def _kb():
    f = lambda i, c, k, v, g=None: CandidateFact(id=i, profile_id=1, category=c, key=k, value=v, group_key=g,
                                                 status="VERIFIED", source="USER")
    return KnowledgeBase([
        f(1, "work_authorization", "authorized:united arab emirates", "yes"),
        f(2, "skill", "Python", "academic"),
        f(3, "education", "degree", "BSc Computer Science", "edu:1"),
        f(4, "experience", "total_professional_years", "0"),
    ], today=dt.date(2026, 9, 1))


def test_match_analysis_is_transparent_and_decision_follows_rules(s):
    job, _ = ingest(s, None, _nj(), [])
    prefs = Preferences(target_roles=["SOC Analyst"], target_locations=["UAE"], min_match_score=50)
    crit = evaluate(job, prefs, _kb())
    by = {c.name: c.status for c in crit}
    assert by["Target role"] == "MATCH"
    assert by["Location"] == "MATCH"
    assert by["Skill: siem"] == "NOT VERIFIED"
    assert by["Skill: python"] == "PARTIAL"
    assert by["Experience"] == "DOES NOT MATCH"
    assert by["Education"] == "MATCH"
    assert by["Work authorization"] == "MATCH"
    sc = score(crit)
    assert 0 < sc < 100
    d = decide(job, crit, sc, prefs, Rules(), True)
    assert d.decision == "SKIP" and any("Experience" in r for r in d.reasons)
    d = decide(job, crit, sc, prefs, Rules(skip_if_experience_exceeds=False), True)
    assert d.decision == "APPLY"
    d = decide(job, crit, sc, prefs, Rules(on_rule_failure="REVIEW"), True)
    assert d.decision == "REVIEW"
    assert decide(job, crit, sc, prefs, Rules(skip_if_experience_exceeds=False), False).decision == "SKIP"


def test_unconfigured_preferences_never_auto_apply(s):
    job, _ = ingest(s, None, _nj(), [])
    crit = evaluate(job, Preferences(), _kb())
    d = decide(job, crit, score(crit), Preferences(), Rules(), True)
    assert d.decision == "SKIP" and "Target roles NOT CONFIGURED" in d.reasons


def test_exclusions_disqualify(s):
    job, _ = ingest(s, None, _nj(), [])
    prefs = Preferences(target_roles=["SOC Analyst"], target_locations=["UAE"], exclude_companies=["acme"])
    crit = evaluate(job, prefs, _kb())
    assert decide(job, crit, score(crit), prefs, Rules(), True).decision == "SKIP"


class _FakeHTTP:
    """Replays response bodies with the documented public API shapes (parser unit test only)."""

    def __init__(self, responses):
        self.responses = responses

    def get_json(self, url, params=None):
        return self.responses[url]


def test_connector_parsers_against_documented_shapes():
    gh = GreenhouseConnector(_FakeHTTP({
        "https://boards-api.greenhouse.io/v1/boards/acme": {"name": "Acme"},
        "https://boards-api.greenhouse.io/v1/boards/acme/jobs": {"jobs": [{
            "id": 42, "title": "SOC Analyst", "updated_at": "2026-09-01T10:00:00-04:00",
            "location": {"name": "Remote"}, "absolute_url": "https://acme.example/jobs?gh_jid=42",
            "content": "&lt;p&gt;Hi&lt;/p&gt;"}]},
    }))
    [j] = gh.fetch("acme", {})
    assert (j.company, j.external_id, j.workplace_type, j.description_text) == ("Acme", "42", "remote", "Hi")
    assert j.apply_url == "https://job-boards.greenhouse.io/acme/jobs/42"

    lv = LeverConnector(_FakeHTTP({"https://api.lever.co/v0/postings/acme": [{
        "id": "u-1", "text": "Analyst", "categories": {"location": "Dubai", "commitment": "Full-time"},
        "workplaceType": "onsite", "createdAt": 1756700000000, "descriptionPlain": "desc", "lists": [],
        "hostedUrl": "https://jobs.lever.co/acme/u-1", "applyUrl": "https://jobs.lever.co/acme/u-1/apply",
        "salaryRange": {"min": 1, "max": 2, "currency": "AED", "interval": "per-month-salary"}}]}))
    [j] = lv.fetch("acme", {})
    assert (j.workplace_type, j.employment_type, j.salary_currency) == ("onsite", "Full-time", "AED")
    assert j.company is None  # Lever API has no company name; stays UNKNOWN unless configured

    ab = AshbyConnector(_FakeHTTP({"https://api.ashbyhq.com/posting-api/job-board/acme": {"jobs": [
        {"id": "a1", "title": "Eng", "employmentType": "FullTime", "location": "Dubai", "isListed": True,
         "workplaceType": "Hybrid", "publishedAt": "2026-09-01T00:00:00Z", "jobUrl": "https://jobs.ashbyhq.com/acme/a1",
         "applyUrl": "https://jobs.ashbyhq.com/acme/a1/application", "descriptionPlain": "d"},
        {"id": "a2", "title": "Hidden", "isListed": False}]}}))
    jobs = ab.fetch("acme", {})
    assert len(jobs) == 1 and jobs[0].employment_type == "full-time" and jobs[0].workplace_type == "hybrid"


def test_non_http_urls_rejected(s):
    import pytest
    from autopilot.jobs.pipeline import InvalidJobData

    with pytest.raises(InvalidJobData):
        ingest(s, None, _nj(url="javascript:alert(1)"), [])
    with pytest.raises(InvalidJobData):
        ingest(s, None, _nj(apply_url="file:///etc/passwd"), [])
