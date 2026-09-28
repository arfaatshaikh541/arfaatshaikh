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
        if not spec["automatable"]:
            p.status = PlatformStatus.NOT_AUTOMATABLE.value
            p.status_reason = spec["notes"]
