"""Static platform registry: what each platform supports and why.

Platforms that do not permit automated use are recorded as NOT_AUTOMATABLE and
have no connector code at all. Their status cannot be changed from the UI.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Platform, PlatformStatus

REGISTRY = [
    {
        "key": "greenhouse", "name": "Greenhouse (employer job boards)", "automatable": True, "requires_login": False,
        "notes": "Discovery: official public Job Board API. Apply: employer's public hosted application form "
                 "(no account needed). Forms may include reCAPTCHA; if a challenge appears the application is "
                 "recorded as VERIFICATION_REQUIRED and never bypassed.",
    },
    {
        "key": "lever", "name": "Lever (employer job boards)", "automatable": True, "requires_login": False,
        "notes": "Discovery: official public Postings API. Apply: public hosted form at jobs.lever.co. Lever forms "
                 "commonly use hCaptcha; such cases are recorded as VERIFICATION_REQUIRED.",
    },
    {
        "key": "ashby", "name": "Ashby (employer job boards)", "automatable": True, "requires_login": False,
        "notes": "Discovery: official public Posting API. Apply: public hosted form at jobs.ashbyhq.com.",
    },
    {
        "key": "generic_portal", "name": "Employer career portal (custom login)", "automatable": True,
        "requires_login": True,
        "notes": "LOGIN TEST ONLY. You configure the login URL, field selectors and a success indicator; the worker "
                 "performs a real login and reports CONNECTED only when the success indicator is observed. "
                 "Automated applying on arbitrary portals is NOT SUPPORTED.",
    },
    {
        "key": "linkedin", "name": "LinkedIn", "automatable": False, "requires_login": True,
        "notes": "NOT AUTOMATABLE. LinkedIn's User Agreement prohibits bots and automated access/scraping, it offers "
                 "no job-application API to individual members, and it employs anti-automation checks that must not "
                 "be evaded. No connector is provided.",
    },
    {
        "key": "indeed", "name": "Indeed", "automatable": False, "requires_login": True,
        "notes": "NOT AUTOMATABLE. Indeed's terms prohibit automated access and scraping; its public APIs are for "
                 "employers/ATS partners, not job seekers. No connector is provided.",
    },
    {
        "key": "bayt", "name": "Bayt.com", "automatable": False, "requires_login": True,
        "notes": "NOT AUTOMATABLE. No public job-seeker API; site terms prohibit automated use. Re-assess only with "
                 "written permission from Bayt.",
    },
    {
        "key": "gulftalent", "name": "GulfTalent", "automatable": False, "requires_login": True,
        "notes": "NOT AUTOMATABLE. No public job-seeker API; site terms prohibit automated use.",
    },
    {
        "key": "naukrigulf", "name": "Naukrigulf", "automatable": False, "requires_login": True,
        "notes": "NOT AUTOMATABLE. No public job-seeker API; site terms prohibit automated use and the site uses "
                 "OTP/anti-bot verification.",
    },
]


# Capability states:
#   SUPPORTED     implemented and tested against the documented interface
#   PENDING_LIVE  implemented; not yet exercised against the live service
#   NOT_IMPLEMENTED  legitimately possible but not built (would need employer-specific work)
#   NOT_AVAILABLE    no such interface exists for applicants
#   NOT_PERMITTED    the platform's terms prohibit automated use
CAPS = ("DISCOVERY", "JOB_DETAILS", "APPLICATION_REDIRECT", "DIRECT_APPLICATION", "AUTOMATED_SUBMISSION",
        "OFFICIAL_API")


def _caps(**kw: str) -> dict:
    return {c: kw.get(c, "NOT_IMPLEMENTED") for c in CAPS}


_ATS_OK = _caps(DISCOVERY="PENDING_LIVE", JOB_DETAILS="PENDING_LIVE", APPLICATION_REDIRECT="PENDING_LIVE",
                DIRECT_APPLICATION="PENDING_LIVE", AUTOMATED_SUBMISSION="PENDING_LIVE",
                OFFICIAL_API="SUPPORTED (public read API)")
_FORBIDDEN = {c: "NOT_PERMITTED" for c in CAPS}
CAPABILITIES = {
    "greenhouse": _ATS_OK, "lever": _ATS_OK, "ashby": _ATS_OK,
    "smartrecruiters": _caps(DISCOVERY="PENDING_LIVE", APPLICATION_REDIRECT="PENDING_LIVE",
                             OFFICIAL_API="SUPPORTED (public Posting API)"),
    "workable": _caps(),
    "icims": _caps(OFFICIAL_API="NOT_AVAILABLE"),
    "workday": _caps(OFFICIAL_API="NOT_AVAILABLE"),
    "oracle_recruiting": _caps(OFFICIAL_API="NOT_AVAILABLE"),
    "sap_successfactors": _caps(OFFICIAL_API="NOT_AVAILABLE"),
    "generic_portal": _caps(),
    "linkedin": _FORBIDDEN, "indeed": _FORBIDDEN, "bayt": _FORBIDDEN, "gulftalent": _FORBIDDEN,
    "naukrigulf": _FORBIDDEN,
}

REGISTRY += [
    {"key": "smartrecruiters", "name": "SmartRecruiters (employer job boards)", "automatable": True,
     "requires_login": False,
     "notes": "Discovery via the public Posting API (api.smartrecruiters.com/v1/companies/{id}/postings). "
              "Applying is NOT IMPLEMENTED: jobs are listed with their application link for you to apply manually."},
    {"key": "workable", "name": "Workable", "automatable": False, "requires_login": False,
     "notes": "NOT IMPLEMENTED. No connector has been built or validated for Workable job boards yet."},
    {"key": "icims", "name": "iCIMS", "automatable": False, "requires_login": True,
     "notes": "NOT IMPLEMENTED. No public applicant API; every employer tenant has its own portal and account."},
    {"key": "workday", "name": "Workday", "automatable": False, "requires_login": True,
     "notes": "NOT IMPLEMENTED. No official public applicant API (the JSON used by career sites is undocumented "
              "and not used). Per-tenant accounts, multi-page flows. Apply manually."},
    {"key": "oracle_recruiting", "name": "Oracle Recruiting Cloud", "automatable": False, "requires_login": True,
     "notes": "NOT IMPLEMENTED. No official public applicant API; per-tenant candidate accounts."},
    {"key": "sap_successfactors", "name": "SAP SuccessFactors", "automatable": False, "requires_login": True,
     "notes": "NOT IMPLEMENTED. No official public applicant API; per-tenant candidate accounts."},
]


def sync_platform_registry(s: Session) -> None:
    for spec in REGISTRY:
        p = s.get(Platform, spec["key"])
        if p is None:
            p = Platform(key=spec["key"])
            s.add(p)
            if not spec["automatable"]:
                p.status = PlatformStatus.NOT_AUTOMATABLE.value
            elif not spec["requires_login"]:
                p.status = PlatformStatus.NO_LOGIN_REQUIRED.value
            else:
                p.status = PlatformStatus.NOT_CONFIGURED.value
        p.name = spec["name"]
        p.automatable = spec["automatable"]
        p.requires_login = spec["requires_login"]
        p.notes = spec["notes"]
        p.capabilities = CAPABILITIES.get(spec["key"], _caps())
        if not spec["automatable"]:
            p.status = (PlatformStatus.NOT_IMPLEMENTED if spec["notes"].startswith("NOT IMPLEMENTED")
                        else PlatformStatus.NOT_AUTOMATABLE).value
            p.status_reason = spec["notes"]
        elif not spec["requires_login"]:
            p.status = PlatformStatus.NO_LOGIN_REQUIRED.value
