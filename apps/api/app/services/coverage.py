"""Where each domain actually has data, stated plainly so the interface never implies worldwide coverage.

coverage_status:
  GLOBAL                 published content that is not tied to a place (the Qur'an text); `content_scope` says FULL or PARTIAL, `scope` what is in it.
  <COUNTRY>_ONLY         published listings exist for exactly one country (e.g. ALGERIA_ONLY).
  REGIONAL               published listings exist for several, but not all, countries; `countries` lists them.
  HIDDEN_PENDING_RIGHTS  records are imported but not shown, because rights or validation are not established.
  NO_VERIFIED_DATA       nothing is imported for this domain.
"""
from __future__ import annotations

import re

GEOGRAPHIC = {"mosques": "mosque", "organisations": "organisation", "events": "event", "charities": "charity", "volunteering": "volunteering", "businesses": "business",
              "professionals": "professional", "health": "health", "jobs": "job"}
# Where a directory's data comes from, as a class: community-contributed map data is not an authority's register. Only mosques have published data today.
DATA_CLASS = {"mosques": "COMMUNITY_DATA"}


def verification_token(published: int, verified: int) -> str:
    if published <= 0 or verified <= 0:
        return "NOT_INDIVIDUALLY_VERIFIED"
    return "FULLY_VERIFIED" if verified >= published else "PARTLY_VERIFIED"


# English names for ISO 3166-1 alpha-2 codes; a code missing here is shown as the bare code, never guessed.
COUNTRY_NAMES = {
    "AE": "United Arab Emirates", "AF": "Afghanistan", "AL": "Albania", "AU": "Australia", "AZ": "Azerbaijan", "BA": "Bosnia and Herzegovina", "BD": "Bangladesh", "BH": "Bahrain",
    "BN": "Brunei", "CA": "Canada", "CN": "China", "DE": "Germany", "DJ": "Djibouti", "DZ": "Algeria", "EG": "Egypt", "ES": "Spain", "ET": "Ethiopia", "FR": "France", "GB": "United Kingdom",
    "ID": "Indonesia", "IN": "India", "IQ": "Iraq", "IR": "Iran", "IT": "Italy", "JO": "Jordan", "KW": "Kuwait", "KZ": "Kazakhstan", "LB": "Lebanon", "LY": "Libya", "MA": "Morocco",
    "ML": "Mali", "MR": "Mauritania", "MY": "Malaysia", "NG": "Nigeria", "NL": "Netherlands", "OM": "Oman", "PK": "Pakistan", "PS": "Palestine", "QA": "Qatar", "RU": "Russia",
    "SA": "Saudi Arabia", "SD": "Sudan", "SE": "Sweden", "SG": "Singapore", "SN": "Senegal", "SO": "Somalia", "SY": "Syria", "TN": "Tunisia", "TR": "Turkey", "US": "United States",
    "YE": "Yemen", "ZA": "South Africa",
}


def country_label(code: str) -> str:
    return COUNTRY_NAMES.get(code, code)


def status_token(code: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", country_label(code).upper()).strip("_") + "_ONLY"


def build_coverage(domains: list[dict], listing_rows: list[dict]) -> dict:
    """domains: rows from readiness.summarise(); listing_rows: {type, country, published, city_known, regions} per country and listing type, published listings only."""
    by_type: dict[str, list[dict]] = {}
    for row in listing_rows:
        by_type.setdefault(row["type"], []).append(row)
    out = []
    for d in domains:
        rec = d["records"]
        item = {"domain": d["domain"], "label": d["label"], "status": d["status"], "published": rec["published"], "hidden": rec["hidden"], "scope": d["scope"], "geographic": d["domain"] in GEOGRAPHIC}
        if d["domain"] in GEOGRAPHIC:
            rows = sorted(by_type.get(GEOGRAPHIC[d["domain"]], []), key=lambda r: r["country"])
            countries = [{"code": r["country"], "name": country_label(r["country"]), "published": r["published"], "listings_with_city": r["city_known"], "listings_without_city": r["published"] - r["city_known"],
                          "regions": r["regions"]} for r in rows]
            item["countries"] = countries
            published_total, verified_total = sum(r["published"] for r in rows), sum(r.get("verified", 0) for r in rows)
            if rows:
                item["verification"] = verification_token(published_total, verified_total)
                item["verified_listings"] = verified_total
                if d["domain"] in DATA_CLASS:
                    item["data_class"] = DATA_CLASS[d["domain"]]
            if len(countries) == 1:
                item["coverage_status"] = status_token(countries[0]["code"])
            elif countries:
                item["coverage_status"] = "REGIONAL"
            else:
                item["coverage_status"] = "HIDDEN_PENDING_RIGHTS" if rec["hidden"] else "NO_VERIFIED_DATA"
            item["statement"] = (f"Listings exist only for: {', '.join(c['name'] for c in countries)}. Absence of a listing elsewhere does not mean absence of a mosque or service." if countries
                                 else "No verified listings are published for this domain.")
        else:
            if rec["published"] > 0:
                item["coverage_status"] = "GLOBAL"
                item["content_scope"] = d["coverage"]
                item["statement"] = f"Published content is not tied to a place. Scope: {d['scope']}"
            else:
                item["coverage_status"] = "HIDDEN_PENDING_RIGHTS" if rec["hidden"] else "NO_VERIFIED_DATA"
                item["statement"] = ("Records are imported but hidden until rights and validation are established." if rec["hidden"] else "Nothing is imported for this domain.")
        out.append(item)
    return {"domains": out, "statement": "Geographic coverage is exactly the countries listed per domain. No domain is described as worldwide unless it is published, non-geographic content."}
