"""Job discovery through official, public, documented job-board APIs.

* Greenhouse Job Board API  – https://developers.greenhouse.io/job-board.html
* Lever Postings API        – https://github.com/lever/postings-api
* Ashby Posting API         – https://developers.ashbyhq.com/docs/public-job-posting-api

These APIs are published by the ATS vendors precisely so job listings can be
read by third parties. They require no authentication for reading.
Missing fields stay None (rendered as UNKNOWN); nothing is filled in.
"""
from __future__ import annotations

import re
from typing import Any

from .base import DiscoveryConnector, NormalizedJob, PermanentError, html_to_text, parse_iso

_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


def _check_identifier(identifier: str) -> str:
    if not _SAFE_ID.match(identifier):
        raise PermanentError(f"Invalid board identifier {identifier!r}")
    return identifier


def _workplace(v: str | None, is_remote: bool | None = None) -> str | None:
    if v:
        t = v.lower().replace("-", "").replace("_", "")
        if "remote" in t:
            return "remote"
        if "hybrid" in t:
            return "hybrid"
        if "onsite" in t or "office" in t:
            return "onsite"
    if is_remote is True:
        return "remote"
    return None


class GreenhouseConnector(DiscoveryConnector):
    key = "greenhouse"
    API = "https://boards-api.greenhouse.io/v1/boards"

    def fetch(self, identifier: str, options: dict[str, Any]) -> list[NormalizedJob]:
        token = _check_identifier(identifier)
        board = self.http.get_json(f"{self.API}/{token}")
        company = options.get("company_name") or board.get("name")
        data = self.http.get_json(f"{self.API}/{token}/jobs", params={"content": "true"})
        out = []
        for j in data.get("jobs", []):
            jid = str(j["id"])
            loc = (j.get("location") or {}).get("name")
            out.append(NormalizedJob(
                platform="greenhouse", board=token, external_id=jid,
                url=j.get("absolute_url") or f"https://job-boards.greenhouse.io/{token}/jobs/{jid}",
                apply_url=f"https://job-boards.greenhouse.io/{token}/jobs/{jid}",
                apply_method="greenhouse_hosted_form",
                title=j.get("title") or "",
                company=j.get("company_name") or company,
                location=loc,
                workplace_type=_workplace(loc),
                description_text=html_to_text(j.get("content")),
                published_at=parse_iso(j.get("first_published") or j.get("updated_at")),
                raw={k: j.get(k) for k in ("id", "internal_job_id", "requisition_id", "updated_at", "first_published",
                                           "departments", "offices", "metadata", "absolute_url")},
            ))
        return out


class LeverConnector(DiscoveryConnector):
    key = "lever"

    def fetch(self, identifier: str, options: dict[str, Any]) -> list[NormalizedJob]:
        company = _check_identifier(identifier)
        base = "https://api.eu.lever.co" if options.get("region") == "eu" else "https://api.lever.co"
        rows = self.http.get_json(f"{base}/v0/postings/{company}", params={"mode": "json"})
        if not isinstance(rows, list):
            raise PermanentError("Unexpected Lever response shape")
        out = []
        for p in rows:
            cats = p.get("categories") or {}
            sal = p.get("salaryRange") or {}
            lists = "\n\n".join(f"{l.get('text', '')}\n{html_to_text(l.get('content')) or ''}" for l in p.get("lists") or [])
            desc = "\n\n".join(x for x in [p.get("descriptionPlain"), lists, p.get("additionalPlain")] if x)
            out.append(NormalizedJob(
                platform="lever", board=company, external_id=str(p["id"]),
                url=p.get("hostedUrl") or f"https://jobs.lever.co/{company}/{p['id']}",
                apply_url=p.get("applyUrl") or f"https://jobs.lever.co/{company}/{p['id']}/apply",
                apply_method="lever_hosted_form",
                title=p.get("text") or "",
                company=options.get("company_name") or None,
                location=cats.get("location") or ", ".join(cats.get("allLocations") or []) or None,
                workplace_type=_workplace(p.get("workplaceType") if p.get("workplaceType") != "unspecified" else None),
                employment_type=cats.get("commitment"),
                salary_min=sal.get("min"), salary_max=sal.get("max"),
                salary_currency=sal.get("currency"), salary_interval=sal.get("interval"),
                salary_text=p.get("salaryDescriptionPlain"),
                description_text=desc or None,
                published_at=parse_iso(p.get("createdAt")),
                raw={k: p.get(k) for k in ("id", "categories", "country", "workplaceType", "createdAt", "hostedUrl",
                                           "applyUrl", "salaryRange")},
            ))
        return out


_ASHBY_EMPLOYMENT = {"FullTime": "full-time", "PartTime": "part-time", "Intern": "internship",
                     "Contract": "contract", "Temporary": "temporary"}


class AshbyConnector(DiscoveryConnector):
    key = "ashby"

    def fetch(self, identifier: str, options: dict[str, Any]) -> list[NormalizedJob]:
        org = _check_identifier(identifier)
        data = self.http.get_json(
            f"https://api.ashbyhq.com/posting-api/job-board/{org}", params={"includeCompensation": "true"}
        )
        out = []
        for j in data.get("jobs", []):
            if j.get("isListed") is False:
                continue
            smin = smax = cur = interval = None
            comp = j.get("compensation") or {}
            for c in comp.get("summaryComponents") or []:
                if c.get("compensationType") == "Salary":
                    smin, smax, cur, interval = c.get("minValue"), c.get("maxValue"), c.get("currencyCode"), c.get("interval")
                    break
            locs = [j.get("location")] + [x.get("location") for x in j.get("secondaryLocations") or []]
            out.append(NormalizedJob(
                platform="ashby", board=org, external_id=str(j["id"]),
                url=j.get("jobUrl") or f"https://jobs.ashbyhq.com/{org}/{j['id']}",
                apply_url=j.get("applyUrl") or f"https://jobs.ashbyhq.com/{org}/{j['id']}/application",
                apply_method="ashby_hosted_form",
                title=j.get("title") or "",
                company=options.get("company_name") or None,
                location=" / ".join(l for l in locs if l) or None,
                workplace_type=_workplace(j.get("workplaceType"), j.get("isRemote")),
                employment_type=_ASHBY_EMPLOYMENT.get(j.get("employmentType") or "", j.get("employmentType")),
                salary_min=smin, salary_max=smax, salary_currency=cur, salary_interval=interval,
                salary_text=comp.get("compensationTierSummary"),
                description_text=j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml")),
                published_at=parse_iso(j.get("publishedAt")),
                raw={k: j.get(k) for k in ("id", "department", "team", "employmentType", "publishedAt", "isRemote",
                                           "workplaceType", "address", "jobUrl", "applyUrl")},
            ))
        return out


class SmartRecruitersConnector(DiscoveryConnector):
    """Public Posting API. Listing only: descriptions need one extra request per job and applying is not
    automated, so jobs are recorded with apply_method 'smartrecruiters_redirect' (manual application)."""

    key = "smartrecruiters"

    def fetch(self, identifier: str, options: dict[str, Any]) -> list[NormalizedJob]:
        company = _check_identifier(identifier)
        out: list[NormalizedJob] = []
        offset = 0
        while offset < 1000:
            data = self.http.get_json(f"https://api.smartrecruiters.com/v1/companies/{company}/postings",
                                      params={"limit": 100, "offset": offset})
            rows = data.get("content") or []
            for p in rows:
                loc = p.get("location") or {}
                place = ", ".join(x for x in [loc.get("city"), loc.get("region"), loc.get("country")] if x) or None
                url = f"https://jobs.smartrecruiters.com/{company}/{p['id']}"
                out.append(NormalizedJob(
                    platform="smartrecruiters", board=company, external_id=str(p["id"]), url=url, apply_url=url,
                    apply_method="smartrecruiters_redirect", title=p.get("name") or "",
                    company=(p.get("company") or {}).get("name") or options.get("company_name"),
                    location=place, workplace_type="remote" if loc.get("remote") else None,
                    employment_type=(p.get("typeOfEmployment") or {}).get("label"),
                    published_at=parse_iso(p.get("releasedDate")),
                    raw={k: p.get(k) for k in ("id", "uuid", "refNumber", "releasedDate", "location", "department",
                                               "function", "experienceLevel", "typeOfEmployment")},
                ))
            total = data.get("totalFound") or 0
            offset += len(rows)
            if not rows or offset >= total:
                break
        return out


DISCOVERY_CONNECTORS: dict[str, type[DiscoveryConnector]] = {
    "smartrecruiters": SmartRecruitersConnector,
    "greenhouse": GreenhouseConnector,
    "lever": LeverConnector,
    "ashby": AshbyConnector,
}
