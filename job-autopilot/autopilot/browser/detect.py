"""Detection of security challenges and submission outcomes.

Challenges are only *detected*. Nothing here solves, hides or bypasses them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from playwright.sync_api import Page

CHALLENGE_FRAME_RE = re.compile(
    r"recaptcha/(api2|enterprise)/(bframe|anchor)|hcaptcha\.com/.*(challenge|checkbox)|challenges\.cloudflare\.com|"
    r"arkoselabs|funcaptcha|captcha-delivery|geo\.captcha", re.I
)
OTP_TEXT_RE = re.compile(
    r"verification code|security code|one[- ]time (pass)?code|enter the code (we|that was) sent|verify your (email|phone)|"
    r"two[- ]factor|2-step verification|authenticator app", re.I
)
CONFIRM_URL_RE = re.compile(r"/(confirmation|thank[-_]?you|thanks|submitted|success|application[-_]?confirmation)\b", re.I)
CONFIRM_TEXT_RE = re.compile(
    r"thank(s| you) for (applying|your application|submitting)|application (has been |was )?(successfully )?"
    r"(submitted|received|sent)|we('ve| have) received your application|your application (is|has been) (in|submitted|received)|"
    r"successfully (applied|submitted)",
    re.I,
)
APP_ID_RE = re.compile(r"(?:application|reference|confirmation)\s*(?:id|number|no\.?|#)\s*[:#]?\s*([A-Z0-9][A-Z0-9-]{3,40})", re.I)


@dataclass
class Challenge:
    kind: str  # captcha | otp | login_wall
    detail: str


_SOLVED_JS = """() => [...document.querySelectorAll(
  'textarea[name="g-recaptcha-response"], textarea[name="h-captcha-response"], input[name="cf-turnstile-response"]')]
  .some(el => (el.value || '').length > 0)"""


def captcha_solved(page: Page) -> bool:
    """True when the page's own CAPTCHA response field has been filled (by the human solving it).

    Read-only inspection of the page's state; nothing is written or solved here."""
    try:
        return bool(page.evaluate(_SOLVED_JS))
    except Exception:
        return False


def detect_challenge(page: Page) -> Challenge | None:
    """A *visible, interactive* challenge that a human must complete (and has not completed yet)."""
    solved = captcha_solved(page)
    for fr in ([] if solved else page.frames):
        if fr.url and CHALLENGE_FRAME_RE.search(fr.url):
            try:
                el = fr.frame_element()
                box = el.bounding_box()
                visible = el.is_visible() and box is not None and box["width"] > 30 and box["height"] > 30
            except Exception:
                visible = False
            if visible:
                return Challenge("captcha", f"Visible challenge frame: {fr.url.split('?')[0]}")
    for sel in ([] if solved else ("iframe[title*='challenge' i]", ".h-captcha iframe", ".cf-turnstile iframe",
                                   "#px-captcha")):
        loc = page.locator(sel)
        if loc.count() and loc.first.is_visible():
            return Challenge("captcha", f"Visible challenge element {sel}")
    try:
        body = page.inner_text("body", timeout=5000)[:20000]
    except Exception:
        body = ""
    if OTP_TEXT_RE.search(body) and page.locator("input:visible").count() <= 8:
        m = OTP_TEXT_RE.search(body)
        return Challenge("otp", f"Verification step detected: '{m.group(0)}'")
    return None


@dataclass
class Outcome:
    kind: str  # confirmed | challenge | validation_errors | unknown
    url: str
    text_excerpt: str | None = None
    application_id: str | None = None
    detail: str | None = None


def visible_errors(page: Page) -> list[str]:
    msgs: list[str] = []
    for sel in ("[aria-invalid='true']", "[role='alert']", ".error:visible", ".field-error", ".error-message",
                "[class*='error' i]:visible"):
        try:
            loc = page.locator(sel)
            for i in range(min(loc.count(), 10)):
                el = loc.nth(i)
                if el.is_visible():
                    t = (el.inner_text(timeout=1000) or el.get_attribute("aria-label") or el.get_attribute("name") or "").strip()
                    if t and len(t) < 300:
                        msgs.append(t)
        except Exception:
            continue
    return list(dict.fromkeys(msgs))[:10]


def wait_for_outcome(page: Page, pre_url: str, pre_text_had_confirmation: bool, timeout_s: float = 45) -> Outcome:
    """Poll the real page after clicking submit until a definitive signal appears."""
    import time

    deadline = time.monotonic() + timeout_s
    last_text = ""
    while time.monotonic() < deadline:
        page.wait_for_timeout(1500)
        url = page.url
        try:
            last_text = page.inner_text("body", timeout=5000)[:30000]
        except Exception:
            continue
        m = CONFIRM_TEXT_RE.search(last_text)
        if (m and not pre_text_had_confirmation) or (CONFIRM_URL_RE.search(url) and url != pre_url and m):
            start = max(0, m.start() - 200)
            idm = APP_ID_RE.search(last_text)
            return Outcome("confirmed", url, last_text[start:m.end() + 300].strip(),
                           idm.group(1) if idm else None, f"matched '{m.group(0)}'")
        ch = detect_challenge(page)
        if ch:
            return Outcome("challenge", url, detail=f"{ch.kind}: {ch.detail}")
    errs = visible_errors(page)
    if errs and page.url == pre_url:
        return Outcome("validation_errors", page.url, detail="; ".join(errs))
    return Outcome("unknown", page.url, last_text[:500] if last_text else None,
                   detail="No confirmation, challenge or validation error detected within timeout")
