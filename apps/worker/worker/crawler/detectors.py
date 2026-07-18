"""Detectors that turn one crawled page's HTML into structured
enrichment signals.

Every detector returns real, extracted data or nothing at all - never a
fabricated or inferred value. Detectors that report an *absence*
(`missing_mobile_viewport`, `weak_page_metadata`) still describe something
genuinely observed on that specific page (no viewport meta tag was found
in this page's own HTML), not a guess about the whole site. Whole-site
absence claims (missing_whatsapp, missing_online_booking, ...) are
computed by `worker.enrichment_tasks` from the union of per-page findings
across the whole crawl, not by any single detector here - see that
module's docstring for why that distinction matters (a limited crawl of a
handful of pages cannot make an absolute claim about a whole site).
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from bs4 import BeautifulSoup

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
WHATSAPP_PATTERN = re.compile(r"wa\.me/|api\.whatsapp\.com/send|whatsapp://send", re.IGNORECASE)
COPYRIGHT_YEAR_PATTERN = re.compile(r"(?:©|\(c\)|copyright)\s*(\d{4})", re.IGNORECASE)

BOOKING_DOMAINS = (
    "calendly.com",
    "opentable.com",
    "resy.com",
    "squareup.com/appointments",
    "acuityscheduling.com",
    "setmore.com",
)
ORDERING_DOMAINS = (
    "ubereats.com",
    "doordash.com",
    "grubhub.com",
    "toasttab.com",
    "chownow.com",
    "square.site",
)
SOCIAL_PATTERNS = {
    "social_facebook": re.compile(r"https?://(?:www\.)?facebook\.com/[^\s\"'<>]+", re.IGNORECASE),
    "social_instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[^\s\"'<>]+", re.IGNORECASE),
    "social_linkedin": re.compile(
        r"https?://(?:www\.)?linkedin\.com/company/[^\s\"'<>]+", re.IGNORECASE
    ),
}


@dataclass
class Signal:
    detector_type: str
    structured_result: dict
    confidence: float
    supporting_snippet: str | None = None


def detect_contact_email(soup: BeautifulSoup) -> list[Signal]:
    signals = []
    seen: set[str] = set()
    for a in soup.select('a[href^="mailto:"]'):
        email = str(a["href"]).removeprefix("mailto:").split("?")[0].strip()
        if email and email.lower() not in seen:
            seen.add(email.lower())
            signals.append(Signal("contact_email", {"email": email}, confidence=0.95))
    for match in EMAIL_PATTERN.finditer(soup.get_text(" ")):
        email = match.group(0)
        if email.lower() not in seen:
            seen.add(email.lower())
            signals.append(
                Signal(
                    "contact_email",
                    {"email": email},
                    confidence=0.7,
                    supporting_snippet=match.group(0),
                )
            )
    return signals


def detect_phone(soup: BeautifulSoup) -> list[Signal]:
    signals = []
    seen: set[str] = set()
    for a in soup.select('a[href^="tel:"]'):
        phone = str(a["href"]).removeprefix("tel:").strip()
        if phone and phone not in seen:
            seen.add(phone)
            signals.append(Signal("phone", {"phone": phone}, confidence=0.95))
    return signals


def detect_whatsapp(soup: BeautifulSoup) -> list[Signal]:
    signals = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        if WHATSAPP_PATTERN.search(href) and href not in seen:
            seen.add(href)
            signals.append(
                Signal("whatsapp", {"url": href}, confidence=0.9, supporting_snippet=href)
            )
    return signals


def detect_booking(soup: BeautifulSoup) -> list[Signal]:
    signals = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        href_lower = href.lower()
        for domain in BOOKING_DOMAINS:
            if domain in href_lower and href not in seen:
                seen.add(href)
                signals.append(Signal("booking", {"url": href, "platform": domain}, confidence=0.9))
                break
    return signals


def detect_ordering(soup: BeautifulSoup) -> list[Signal]:
    signals = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        href_lower = href.lower()
        for domain in ORDERING_DOMAINS:
            if domain in href_lower and href not in seen:
                seen.add(href)
                signals.append(
                    Signal("ordering", {"url": href, "platform": domain}, confidence=0.9)
                )
                break
    return signals


def detect_social_links(soup: BeautifulSoup) -> list[Signal]:
    signals = []
    seen: set[str] = set()
    for detector_type, pattern in SOCIAL_PATTERNS.items():
        for a in soup.find_all("a", href=True):
            match = pattern.match(str(a["href"]))
            if match and match.group(0) not in seen:
                seen.add(match.group(0))
                signals.append(Signal(detector_type, {"url": match.group(0)}, confidence=0.9))
    return signals


def detect_missing_mobile_viewport(soup: BeautifulSoup) -> list[Signal]:
    if soup.find("meta", attrs={"name": "viewport"}) is not None:
        return []
    return [Signal("missing_mobile_viewport", {}, confidence=1.0)]


def detect_weak_page_metadata(soup: BeautifulSoup) -> list[Signal]:
    title = soup.title.get_text(strip=True) if soup.title else ""
    description_tag = soup.find("meta", attrs={"name": "description"})
    description = ""
    if description_tag is not None:
        description = str(description_tag.get("content", "")).strip()
    if title and len(title) >= 10 and description:
        return []
    return [
        Signal(
            "weak_page_metadata",
            {"title": title, "has_description": bool(description)},
            confidence=0.8,
        )
    ]


def detect_outdated_copyright_year(soup: BeautifulSoup, *, current_year: int) -> list[Signal]:
    match = COPYRIGHT_YEAR_PATTERN.search(soup.get_text(" "))
    if not match:
        return []
    year = int(match.group(1))
    if year > current_year or current_year - year < 2:
        return []
    return [
        Signal(
            "outdated_copyright_year",
            {"year": year},
            confidence=0.6,
            supporting_snippet=match.group(0),
        )
    ]


def detect_missing_contact_form(soup: BeautifulSoup) -> list[Signal]:
    if soup.find("form") is not None:
        return []
    return [Signal("missing_contact_form", {}, confidence=0.7)]


# Every per-page detector, in the order their findings are collected.
ALL_PAGE_DETECTORS = (
    detect_contact_email,
    detect_phone,
    detect_whatsapp,
    detect_booking,
    detect_ordering,
    detect_social_links,
    detect_missing_mobile_viewport,
    detect_weak_page_metadata,
    detect_missing_contact_form,
)


def run_all_detectors(html_text: str, *, current_year: int | None = None) -> list[Signal]:
    """Runs every per-page detector against one page's HTML and returns
    the combined list of signals actually found on that page."""
    soup = BeautifulSoup(html_text, "html.parser")
    signals: list[Signal] = []
    for detector in ALL_PAGE_DETECTORS:
        signals.extend(detector(soup))
    signals.extend(
        detect_outdated_copyright_year(soup, current_year=current_year or datetime.now(UTC).year)
    )
    return signals
