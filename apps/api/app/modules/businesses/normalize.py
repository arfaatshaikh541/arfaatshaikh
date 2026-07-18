"""Pure normalization helpers shared by discovery upsert
(`repositories.upsert_business_from_discovery`) and the deduplication
matching engine (`dedup.py`). Kept dependency-free (no DB access) and in
their own module specifically so both can import them without either
importing the other.
"""

import re
from urllib.parse import urlparse

_NAME_NOISE_PATTERN = re.compile(r"[^\w\s]")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Lowercased, punctuation-stripped, whitespace-collapsed - "Joe's
    Pizza!" and "JOES PIZZA" both normalize to "joes pizza"."""
    lowered = name.strip().lower()
    stripped = _NAME_NOISE_PATTERN.sub("", lowered)
    return _WHITESPACE_PATTERN.sub(" ", stripped).strip()


def normalize_address(address: str) -> str:
    lowered = address.strip().lower()
    stripped = _NAME_NOISE_PATTERN.sub("", lowered)
    return _WHITESPACE_PATTERN.sub(" ", stripped).strip()


def normalize_phone(phone: str) -> str | None:
    """Digits only - "+1 (206) 555-0100" and "1-206-555-0100" both
    normalize to "12065550100". Deliberately not stripped to a fixed
    trailing-digit count (e.g. "last 7 digits"): that would treat two
    different area codes' numbers as a match, which is exactly the kind
    of loose comparison "conservative" matching rules out."""
    digits = re.sub(r"\D", "", phone)
    return digits or None


def canonical_domain(url: str) -> str | None:
    try:
        netloc = urlparse(url if "//" in url else f"//{url}").netloc.lower()
    except ValueError:
        return None
    return netloc.removeprefix("www.") or None
